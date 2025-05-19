from . import hp_bp
from flask import jsonify, render_template, request, Response
import pandas as pd
import json
import aiohttp
import asyncio
from requests.auth import HTTPBasicAuth
import time
from .processors import processar_hp_data
from .plotter import processar_plotter_data
from collections import deque

# Configurações da API WooCommerce
WOOCOMMERCE_CONSUMER_KEY = 'ck_131b451fd7b97ebbb0dfaab74ebd5ce3868e50fe'
WOOCOMMERCE_CONSUMER_SECRET = 'cs_2fd8a064e9f6df929a2d63c7eceb26dea344b517'

# Variável global para armazenar o progresso
progresso_atual = {
    'loteAtual': 0,
    'total': 0,
    'status': 'Aguardando...',
    'erros': 0,
    'sucessos': 0
}

async def enviar_lote(session, lote, numero_lote, url, max_tentativas=5):
    batch_payload = {
        "create": lote
    }
    
    tentativas = 0
    while tentativas < max_tentativas:
        try:
            # Validação dos produtos
            for produto in lote:
                if not all([produto.get('name'), produto.get('sku'), produto.get('price')]):
                    raise Exception(f"Produto inválido no lote {numero_lote}: {produto}")

            async with session.post(
                url,
                auth=aiohttp.BasicAuth(WOOCOMMERCE_CONSUMER_KEY, WOOCOMMERCE_CONSUMER_SECRET),
                json=batch_payload,
                timeout=300  # 5 minutos
            ) as response:
                if response.status == 200:
                    print(f"Lote {numero_lote} enviado com sucesso!")
                    progresso_atual['sucessos'] += 1
                    return True
                else:
                    raise Exception(f"Erro API: {response.status} - {await response.text()}")

        except Exception as e:
            tentativas += 1
            print(f"Tentativa {tentativas} falhou para o lote {numero_lote}: {str(e)}")
            progresso_atual['erros'] += 1
            
            if tentativas == max_tentativas:
                print(f"Erro crítico: lote {numero_lote} falhou após {max_tentativas} tentativas.")
                return False
            
            # Espera progressiva entre tentativas (2, 4, 8, 16, 32 segundos)
            await asyncio.sleep(2 ** tentativas)
    
    return False

@hp_bp.route('/progresso')
def progresso():
    def gerar_eventos():
        while True:
            yield f"data: {json.dumps(progresso_atual)}\n\n"
            time.sleep(1)
    
    return Response(gerar_eventos(), mimetype='text/event-stream')

@hp_bp.route('/hp', methods=['GET'])
def listar_produtos():
    return render_template('hp_upload.html')

@hp_bp.route('/hp', methods=['POST'])
async def processar_arquivo():
    global progresso_atual
    arquivo_produtos = request.files.get('arquivo_produtos')
    arquivo_precos = request.files.get('arquivo_precos')
    
    if not arquivo_produtos or not arquivo_precos:
        return jsonify({'erro': 'Por favor, envie ambos os arquivos (produtos e preços)'}), 400

    try:
        produtos_processados = processar_hp_data(arquivo_produtos, arquivo_precos)
        
        # Cria um JSON e salva na pasta
        with open('produtos_processados.json', 'w') as json_file:
            json.dump(produtos_processados, json_file, ensure_ascii=False, indent=4)
        
        await deletar_todos_produtos()

        url = "https://ecommerce.microware.com.br/hp/wp-json/wc/v3/products/batch"
        
        total_produtos = len(produtos_processados)
        print(f"Iniciando envio de {total_produtos} produtos em batch...")
        progresso_atual['total'] = (total_produtos + 9) // 10
        progresso_atual['erros'] = 0
        progresso_atual['sucessos'] = 0

        # Configuração do cliente HTTP assíncrono
        async with aiohttp.ClientSession() as session:
            # Divide os produtos em lotes de 10
            lotes = [produtos_processados[i:i+10] for i in range(0, total_produtos, 10)]
            tarefas = []
            fila_reprocessamento = deque()
            
            # Cria tarefas assíncronas para cada lote
            for i, lote in enumerate(lotes, 1):
                progresso_atual['loteAtual'] = i
                progresso_atual['status'] = f'Enviando lote {i} de {progresso_atual["total"]}'
                tarefa = enviar_lote(session, lote, i, url)
                tarefas.append(tarefa)
            
            # Executa todas as tarefas em paralelo, limitando a 5 requisições simultâneas
            resultados = await asyncio.gather(*tarefas, return_exceptions=True)
            
            # Verifica os resultados e adiciona lotes com erro à fila de reprocessamento
            for i, resultado in enumerate(resultados, 1):
                if not resultado:
                    fila_reprocessamento.append((lotes[i-1], i))
            
            # Reprocessa lotes com erro
            while fila_reprocessamento:
                lote, numero_lote = fila_reprocessamento.popleft()
                print(f"Reprocessando lote {numero_lote}...")
                progresso_atual['status'] = f'Reprocessando lote {numero_lote} de {progresso_atual["total"]}'
                
                sucesso = await enviar_lote(session, lote, numero_lote, url, max_tentativas=10)
                if not sucesso:
                    # Se ainda falhar, salva o lote para processamento manual
                    with open(f'lote_falha_{numero_lote}.json', 'w') as f:
                        json.dump(lote, f, ensure_ascii=False, indent=4)

        print("\nProcesso de envio concluído!")
        progresso_atual['status'] = f'Concluído! Sucessos: {progresso_atual["sucessos"]}, Erros: {progresso_atual["erros"]}'
        return jsonify({
            'mensagem': 'Processo de envio concluído.',
            'dados': produtos_processados,
            'estatisticas': {
                'sucessos': progresso_atual['sucessos'],
                'erros': progresso_atual['erros']
            }
        })

    except Exception as erro_geral:
        print(f"Erro geral no envio: {str(erro_geral)}")
        with open('erro_geral_envio.txt', 'w') as f:
            f.write(str(erro_geral))
        progresso_atual['status'] = 'Erro!'
        return jsonify({'erro': str(erro_geral)})

@hp_bp.route('/hp/plotter', methods=['POST'])
async def processar_plotter():
    global progresso_atual
    arquivo_plotter = request.files.get('arquivo_plotter')
    
    if not arquivo_plotter:
        return jsonify({'erro': 'Por favor, envie o arquivo de plotter'}), 400

    try:
        
        # Processar o arquivo de plotter
        produtos_plotter = processar_plotter_data(arquivo_plotter)
        
        # Deleta todos os produtos da categoria 24("Impressora")
        await deletar_todos_produtos_plotter()
        
        url = "https://ecommerce.microware.com.br/hp/wp-json/wc/v3/products/batch"
        
        
        total_produtos = len(produtos_plotter)
        print(f"Iniciando envio de {total_produtos} produtos em batch...")
        progresso_atual['total'] = (total_produtos + 9) // 10
        progresso_atual['erros'] = 0
        progresso_atual['sucessos'] = 0

        # Configuração do cliente HTTP assíncrono
        async with aiohttp.ClientSession() as session:
            # Divide os produtos em lotes de 10
            lotes = [produtos_plotter[i:i+10] for i in range(0, total_produtos, 10)]
            tarefas = []
            fila_reprocessamento = deque()
            
            # Cria tarefas assíncronas para cada lote
            for i, lote in enumerate(lotes, 1):
                progresso_atual['loteAtual'] = i
                progresso_atual['status'] = f'Enviando lote {i} de {progresso_atual["total"]}'
                tarefa = enviar_lote(session, lote, i, url)
                tarefas.append(tarefa)
            
            # Executa todas as tarefas em paralelo, limitando a 5 requisições simultâneas
            resultados = await asyncio.gather(*tarefas, return_exceptions=True)
            
            # Verifica os resultados e adiciona lotes com erro à fila de reprocessamento
            for i, resultado in enumerate(resultados, 1):
                if not resultado:
                    fila_reprocessamento.append((lotes[i-1], i))
            
            # Reprocessa lotes com erro
            while fila_reprocessamento:
                lote, numero_lote = fila_reprocessamento.popleft()
                print(f"Reprocessando lote {numero_lote}...")
                progresso_atual['status'] = f'Reprocessando lote {numero_lote} de {progresso_atual["total"]}'
                
                sucesso = await enviar_lote(session, lote, numero_lote, url, max_tentativas=10)
                if not sucesso:
                    # Se ainda falhar, salva o lote para processamento manual
                    with open(f'lote_falha_{numero_lote}.json', 'w') as f:
                        json.dump(lote, f, ensure_ascii=False, indent=4)

        print("\nProcesso de envio concluído!")
        

        return jsonify({
            'mensagem': 'Arquivo de plotter enviado com sucesso',
            'estatisticas': {
                'sucessos': 0,
                'erros': 0
            }
        })

    except Exception as erro_geral:
        print(f"Erro geral no processamento do plotter: {str(erro_geral)}")
        with open('erro_geral_plotter.txt', 'w') as f:
            f.write(str(erro_geral))
        progresso_atual['status'] = 'Erro!'
        return jsonify({'erro': str(erro_geral)})

async def deletar_produto(session, produto_id, auth):
    url = f"https://ecommerce.microware.com.br/hp/wp-json/wc/v3/products/{produto_id}?force=true"
    try:
        async with session.delete(url, auth=auth) as response:
            if response.status == 200:
                print(f"Produto {produto_id} deletado com sucesso.")
                return True
            else:
                print(f"Erro ao deletar produto {produto_id}: {response.status}")
                return False
    except Exception as e:
        print(f"Erro ao deletar produto {produto_id}: {str(e)}")
        return False

async def deletar_todos_produtos():
    url_base = "https://ecommerce.microware.com.br/hp/wp-json/wc/v3/products"
    auth = aiohttp.BasicAuth(WOOCOMMERCE_CONSUMER_KEY, WOOCOMMERCE_CONSUMER_SECRET)
    todos_ids = []

    # Primeiro, coletamos todos os IDs
    async with aiohttp.ClientSession() as session:
        page = 1
        while True:
            async with session.get(
                url_base,
                auth=auth,
                params={"per_page": 100, "page": page}
            ) as response:
                produtos = await response.json()
                if not produtos:
                    break
                
                # Filtra os produtos que NÃO pertencem à categoria 24
                for produto in produtos:
                    categorias = produto.get('categories', [])
                    if not any(cat['id'] == 24 for cat in categorias):
                        todos_ids.append(produto["id"])
                
                page += 1

    if not todos_ids:
        print("Nenhum produto encontrado fora da categoria 24.")
        return

    print(f"Encontrados {len(todos_ids)} produtos fora da categoria 24.")

    # Agora deletamos em grupos de 5
    async with aiohttp.ClientSession() as session:
        for i in range(0, len(todos_ids), 5):
            grupo_ids = todos_ids[i:i+5]
            tarefas = [deletar_produto(session, id, auth) for id in grupo_ids]
            await asyncio.gather(*tarefas)
            print(f"Grupo de {len(grupo_ids)} produtos processado.")

    print("Todos os produtos (exceto categoria 24) foram deletados com sucesso!")
    
    
async def deletar_todos_produtos_plotter():
    url_base = "https://ecommerce.microware.com.br/hp/wp-json/wc/v3/products"
    auth = aiohttp.BasicAuth(WOOCOMMERCE_CONSUMER_KEY, WOOCOMMERCE_CONSUMER_SECRET)
    todos_ids = []

    # Primeiro, coletamos todos os IDs dos produtos da categoria 24
    async with aiohttp.ClientSession() as session:
        page = 1
        while True:
            async with session.get(
                url_base,
                auth=auth,
                params={"per_page": 100, "page": page, "category": 24}
            ) as response:
                produtos = await response.json()
                if not produtos:
                    break
                todos_ids.extend([produto["id"] for produto in produtos])
                page += 1

    if not todos_ids:
        print("Nenhum produto encontrado na categoria 24.")
        return

    print(f"Encontrados {len(todos_ids)} produtos na categoria 24.")

    # Agora deletamos em grupos de 5
    async with aiohttp.ClientSession() as session:
        for i in range(0, len(todos_ids), 5):
            grupo_ids = todos_ids[i:i+5]
            tarefas = [deletar_produto(session, id, auth) for id in grupo_ids]
            await asyncio.gather(*tarefas)
            print(f"Grupo de {len(grupo_ids)} produtos processado.")

    print("Todos os produtos da categoria 24 foram deletados com sucesso!")
    


import pandas as pd
import json
import requests

def processar_cisco_data(cisco_data, valor_dolar=None, tipo_lista='real'):
    if tipo_lista == 'real':
        return processar_lista_real(cisco_data)
    elif tipo_lista == 'dolar':
        if not valor_dolar:
            raise ValueError("Valor do dólar é obrigatório para lista em dólar")
        return processar_lista_dolar(cisco_data, valor_dolar)
    else:
        raise ValueError(f"Tipo de lista inválido: {tipo_lista}")

def processar_lista_real(cisco_data):
    print("Processando lista Cisco em reais")
    
    # Limpa os espaços das colunas
    cisco_data.columns = cisco_data.columns.str.strip()
    
    produtos = cisco_data.to_dict('records')
    produtos_processados = []
    
    for produto in produtos:
        try:
            # Pula linhas que não são produtos válidos
            if not eh_produto_valido(produto):
                continue

            #pular se o Part Number for vazio e o NCM estiver vazio
            if produto.get('Part Number') == '' and produto.get('NCM') == '':
                continue

            # Converte o preço para float usando a função específica para formato brasileiro
            preco_str = str(produto.get('Valor Total', '0')).strip()
            try:
                preco = converter_preco_br_para_float(preco_str)
            except ValueError as e:
                print(f"Erro ao converter preço '{preco_str}' para número no produto {produto.get('Part Number', 'ID não encontrado')}")
                continue

            preco_venda = preco / (1 - (20 / 100))

            # Validação adicional dos campos antes de criar o produto
            nome = str(produto.get('Descrição', '')).strip()
            sku = str(produto.get('Part Number', '')).strip()
            
            if nome.lower() == 'nan' or sku.lower() == 'nan':
                print(f"Pulando produto com nome ou SKU inválido: {produto.get('Part Number', 'ID não encontrado')}")
                continue

            produto_data = {
                'name': nome,
                'sku': sku,
                'short_description': nome,
                'description': nome,
                'price': preco_venda,
                'regular_price': preco_venda,
                'stock_quantity': 10,
                'manage_stock': True,
            }
        except (ValueError, TypeError) as e:
            print(f"Erro ao processar produto {produto.get('Product ID', 'ID não encontrado')}: {str(e)}")
            continue

        produtos_processados.append(produto_data)
    return produtos_processados

def converter_preco_br_para_float(preco_str):
    """
    Converte um preço no formato brasileiro (ex: 1.433,46) para float
    """
    try:
        # Remove todos os pontos de milhar
        preco_sem_pontos = preco_str.replace('.', '')
        # Substitui a vírgula por ponto para o formato float
        preco_float = preco_sem_pontos.replace(',', '.')
        return float(preco_float)
    except (ValueError, AttributeError):
        raise ValueError(f"Formato de preço inválido: {preco_str}")

def eh_produto_valido(produto):
    """
    Verifica se a linha contém um produto válido
    """
    # Verifica se tem Part Number válido
    part_number = str(produto.get('Part Number', '')).strip()
    if not part_number or part_number == 'nan' or part_number == 'Part Number' or part_number.lower() == 'nan':
        return False
    
    # Verifica se tem descrição válida
    descricao = str(produto.get('Descrição', '')).strip()
    if not descricao or descricao == 'nan' or descricao == 'Descrição' or descricao.lower() == 'nan':
        return False
    
    # Verifica se tem valor total válido
    valor_total = str(produto.get('Valor Total', '')).strip()
    if not valor_total or valor_total == 'Valor Total' or 'PTAX' in valor_total or 'cotação' in valor_total or valor_total.lower() == 'nan':
        return False
    
    return True

def processar_lista_dolar(cisco_data, valor_dolar):
    print("Processando lista Cisco em dólares")
    
    # Limpa os espaços das colunas
    cisco_data.columns = cisco_data.columns.str.strip()
    
    produtos = cisco_data.to_dict('records')
    produtos_processados = []
    
    for produto in produtos:
        try:
            # Pula linhas que não são produtos válidos
            if not eh_produto_valido(produto):
                continue

            #pular se o Part Number for vazio e o NCM estiver vazio
            if produto.get('Part Number') == '' and produto.get('NCM') == '':
                continue

            # Converte o preço para float usando a função específica para formato brasileiro
            preco_str = str(produto.get('Valor Total', '0')).strip()
            try:
                preco = converter_preco_br_para_float(preco_str)
            except ValueError as e:
                print(f"Erro ao converter preço '{preco_str}' para número no produto {produto.get('Part Number', 'ID não encontrado')}")
                continue

            preco_dolar = preco * valor_dolar
            preco_venda = preco_dolar / (1 - (20 / 100))

            # Validação adicional dos campos antes de criar o produto
            nome = str(produto.get('Descrição', '')).strip()
            sku = str(produto.get('Part Number', '')).strip()
            
            if nome.lower() == 'nan' or sku.lower() == 'nan':
                print(f"Pulando produto com nome ou SKU inválido: {produto.get('Part Number', 'ID não encontrado')}")
                continue

            produto_data = {
                'name': nome,
                'sku': sku,
                'short_description': nome,
                'description': nome,
                'price': preco_venda,
                'regular_price': preco_venda,
                'stock_quantity': 10,
                'manage_stock': True,
            }
        except (ValueError, TypeError) as e:
            print(f"Erro ao processar produto {produto.get('Product ID', 'ID não encontrado')}: {str(e)}")
            continue

        produtos_processados.append(produto_data)
    return produtos_processados

def processar_attributes(product):
    """
    Processa os atributos do produto Cisco
    """
    # TODO: Implementar a lógica de processamento de atributos da Cisco
    pass

def processar_fotos(product):
    """
    Processa as fotos do produto Cisco
    """
    # TODO: Implementar a lógica de processamento de fotos da Cisco
    pass
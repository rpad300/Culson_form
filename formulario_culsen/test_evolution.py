#!/usr/bin/env python3
"""
Script de teste para Evolution API
Este script testa a conexão e funcionalidades básicas do Evolution API
"""

import os
import sys
import json
from typing import Dict, Any
import time

# Adicionar o diretório utils ao path
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))

try:
    from evopai import EvolutionAPI, create_evolution_client, load_evolution_config
except ImportError as e:
    print(f"Erro ao importar módulo Evolution API: {e}")
    print("Certifique-se de que o arquivo utils/evopai.py existe e está configurado corretamente.")
    sys.exit(1)

def print_separator(title: str):
    """Imprime um separador visual com título"""
    print("\n" + "="*60)
    print(f" {title} ")
    print("="*60)

def test_configuration():
    """Testa se as configurações estão corretas"""
    print_separator("TESTE DE CONFIGURAÇÃO")
    
    try:
        config = load_evolution_config()
        print("✅ Configurações carregadas com sucesso:")
        for key, value in config.items():
            if 'key' in key.lower() or 'token' in key.lower():
                # Mascarar chaves sensíveis
                masked_value = value[:8] + "*" * (len(value) - 8) if len(value) > 8 else "****"
                print(f"   {key}: {masked_value}")
            else:
                print(f"   {key}: {value}")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao carregar configurações: {e}")
        print("\nVerifique se as seguintes variáveis de ambiente estão configuradas:")
        print("   - EVOLUTION_API_URL")
        print("   - EVOLUTION_API_KEY")
        print("   - EVOLUTION_INSTANCE_NAME (opcional)")
        return False

def test_connection():
    """Testa a conexão com a Evolution API"""
    print_separator("TESTE DE CONEXÃO")
    
    try:
        evolution = create_evolution_client()
        print(f"✅ Cliente Evolution API criado com sucesso")
        print(f"   URL Base: {evolution.base_url}")
        print(f"   Instância: {evolution.instance_name}")
        return evolution
        
    except Exception as e:
        print(f"❌ Erro ao criar cliente Evolution API: {e}")
        return None

def test_instance_status(evolution: EvolutionAPI):
    """Testa o status da instância"""
    print_separator("TESTE DE STATUS DA INSTÂNCIA")
    
    try:
        status = evolution.get_instance_status()
        print("✅ Status da instância obtido com sucesso:")
        print(json.dumps(status, indent=2, ensure_ascii=False))
        return status
        
    except Exception as e:
        print(f"❌ Erro ao obter status da instância: {e}")
        print("Isso pode indicar que:")
        print("   - A instância não existe ainda")
        print("   - A URL da API está incorreta")
        print("   - A chave de API está inválida")
        print("   - O serviço Evolution API não está rodando")
        return None

def test_qr_code(evolution: EvolutionAPI):
    """Testa a obtenção do QR Code"""
    print_separator("TESTE DE QR CODE")
    
    try:
        qr_response = evolution.get_qr_code()
        print("✅ QR Code obtido com sucesso!")
        
        if 'base64' in qr_response:
            print("   QR Code disponível em base64")
            # Salvar QR code em arquivo para visualização
            qr_data = qr_response['base64']
            if qr_data.startswith('data:image'):
                # Remover prefixo data:image
                qr_data = qr_data.split(',')[1]
            
            try:
                import base64
                with open('qr_code.png', 'wb') as f:
                    f.write(base64.b64decode(qr_data))
                print("   QR Code salvo como 'qr_code.png'")
            except Exception as e:
                print(f"   Erro ao salvar QR Code: {e}")
        
        print(json.dumps(qr_response, indent=2, ensure_ascii=False))
        return qr_response
        
    except Exception as e:
        print(f"❌ Erro ao obter QR Code: {e}")
        return None

def test_instance_creation(evolution: EvolutionAPI):
    """Testa a criação de uma nova instância"""
    print_separator("TESTE DE CRIAÇÃO DE INSTÂNCIA")
    
    try:
        instance_config = {
            "webhook": {
                "url": os.getenv('EVOLUTION_WEBHOOK_URL', ''),
                "webhook_by_events": True,
                "webhook_base64": True
            },
            "settings": {
                "reject_call": False,
                "msg_call": "Desculpe, não posso atender chamadas no momento.",
                "groups_ignore": True,
                "always_online": False,
                "read_messages": False,
                "read_status": False
            }
        }
        
        result = evolution.create_instance(instance_config)
        print("✅ Instância criada com sucesso!")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return result
        
    except Exception as e:
        print(f"❌ Erro ao criar instância: {e}")
        return None

def test_phone_formatting(evolution: EvolutionAPI):
    """Testa a formatação de números de telefone"""
    print_separator("TESTE DE FORMATAÇÃO DE TELEFONES")
    
    test_numbers = [
        "11999999999",
        "(11) 99999-9999",
        "+55 11 99999-9999",
        "5511999999999"
    ]
    
    print("Testando formatação de números:")
    for number in test_numbers:
        formatted = evolution.format_phone_number(number)
        print(f"   {number} → {formatted}")
    
    print("\n✅ Formatação de telefones testada com sucesso!")

def main():
    """Função principal do teste"""
    print("🚀 INICIANDO TESTES DO EVOLUTION API")
    print("Este script irá testar a configuração e conectividade com a Evolution API")
    
    # Teste 1: Configuração
    if not test_configuration():
        return
    
    # Teste 2: Conexão
    evolution = test_connection()
    if not evolution:
        return
    
    # Teste 3: Formatação de telefones
    test_phone_formatting(evolution)
    
    # Teste 4: Status da instância
    status = test_instance_status(evolution)
    
    # Se a instância não existir, tentar criar
    if status is None:
        print("\n🔄 Tentando criar nova instância...")
        creation_result = test_instance_creation(evolution)
        if creation_result:
            print("⏳ Aguardando alguns segundos para a instância se conectar...")
            time.sleep(5)
            status = test_instance_status(evolution)
    
    # Teste 5: QR Code (se necessário)
    if status and 'state' in status:
        if status['state'] == 'close' or 'qr' in str(status).lower():
            test_qr_code(evolution)
    
    print_separator("RESUMO DOS TESTES")
    print("✅ Configuração: OK")
    print("✅ Conexão: OK")
    print("✅ Formatação: OK")
    print(f"{'✅' if status else '❌'} Status da Instância: {'OK' if status else 'ERRO'}")
    
    if status and 'state' in status:
        state = status['state']
        if state == 'open':
            print("✅ WhatsApp conectado e pronto para uso!")
        elif state == 'close':
            print("⚠️  WhatsApp não conectado - escaneie o QR Code")
        else:
            print(f"ℹ️  Estado do WhatsApp: {state}")
    
    print("\n🎉 Testes concluídos!")
    print("Se houver erros, verifique:")
    print("   1. Se a Evolution API está rodando")
    print("   2. Se as variáveis de ambiente estão configuradas")
    print("   3. Se a URL e chave de API estão corretas")

if __name__ == "__main__":
    main() 
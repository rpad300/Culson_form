#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script de teste para verificar acesso aos formulários do Google Sheets
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.sheets import get_all_forms

def test_formularios():
    print("=== TESTE DE ACESSO AOS FORMULÁRIOS ===")
    print()
    
    try:
        print("1. Tentando obter formulários da planilha...")
        formularios = get_all_forms(force_refresh=True)
        
        print(f"✅ Sucesso! Encontrados {len(formularios)} formulários")
        print()
        
        if formularios:
            print("📋 FORMULÁRIOS ENCONTRADOS:")
            print("-" * 50)
            
            for i, form in enumerate(formularios, 1):
                print(f"{i}. ID: {form.get('ID', 'N/A')}")
                print(f"   Nome: {form.get('Nome', 'N/A')}")
                print(f"   Descrição: {form.get('Descricao', 'N/A')}")
                print(f"   Ativo: {form.get('Ativo', 'N/A')}")
                print(f"   Data Criação: {form.get('DataCriacao', 'N/A')}")
                print()
        else:
            print("⚠️  Nenhum formulário encontrado na planilha")
            
    except Exception as e:
        print(f"❌ ERRO: {str(e)}")
        import traceback
        print()
        print("DETALHES DO ERRO:")
        print(traceback.format_exc())

if __name__ == "__main__":
    test_formularios() 
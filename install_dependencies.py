import os
import sys
import subprocess

def install_dependencies():
    """
    Instala as dependências listadas no arquivo requirements.txt
    """
    print("Iniciando instalação das dependências...")
    
    try:
        # Verificar se o arquivo requirements.txt existe
        if not os.path.exists('requirements.txt'):
            print("Erro: Arquivo requirements.txt não encontrado!")
            return False
        
        # Instalar dependências
        print("Instalando pacotes do requirements.txt...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        
        print("\nTodas as dependências foram instaladas com sucesso!")
        print("\nPara executar a aplicação, use o comando:")
        print("python app.py")
        
        return True
    
    except subprocess.CalledProcessError as e:
        print(f"Erro ao instalar dependências: {e}")
        return False
    except Exception as e:
        print(f"Erro inesperado: {e}")
        return False

if __name__ == "__main__":
    install_dependencies() 
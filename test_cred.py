from utils.credentials_helper import get_credentials
print('Testando credenciais...')
credentials = get_credentials(['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
print(f'Credenciais obtidas: {credentials is not None}')
if credentials:
    print(f'Email: {credentials.service_account_email}')

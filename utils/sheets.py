import gspread
from google.oauth2.service_account import Credentials
import datetime
import os
import logging
import traceback
import json

# Configurar logger
logger = logging.getLogger('formulario_culsen.sheets')

# Define scopes
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# Get current directory
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_PATH = os.path.join(current_dir, 'credentials.json')

def get_sheet_client():
    """Returns an authenticated Google Sheets client"""
    try:
        logger.info(f"Tentando autenticar com credenciais em: {CREDENTIALS_PATH}")
        if not os.path.exists(CREDENTIALS_PATH):
            logger.error(f"Arquivo de credenciais não encontrado: {CREDENTIALS_PATH}")
            raise FileNotFoundError(f"Arquivo de credenciais não encontrado: {CREDENTIALS_PATH}")
            
        credentials = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPES)
        client = gspread.authorize(credentials)
        logger.info("Autenticação bem-sucedida")
        return client
    except Exception as e:
        logger.error(f"Erro ao autenticar com Google: {str(e)}")
        logger.error(traceback.format_exc())
        raise

def get_config():
    """Get configuration values from the Config sheet"""
    try:
        logger.info("Obtendo configurações da planilha...")
        client = get_sheet_client()
        
        # Usar ID direto em vez do nome da planilha
        SPREADSHEET_ID = "1UvH63UVLS8KkQJIh6y9hOvygOv2H6GWGZvKTAKMKFzc"
        logger.info(f"Tentando abrir a planilha com ID: {SPREADSHEET_ID}")
        
        sheet = client.open_by_key(SPREADSHEET_ID)
        
        try:
            logger.info("Tentando acessar a aba 'Config'")
            config_sheet = sheet.worksheet("Config")
            
            # Obter todos os valores da planilha como células brutas
            logger.info("Lendo todos os valores da aba Config")
            all_values = config_sheet.get_all_values()
            
            # Converter para dicionário
            config = {}
            
            # Processar diretamente cada linha, considerando que a coluna A contém a chave e a coluna B o valor
            for row in all_values:
                if len(row) >= 2 and row[0]:  # Se tiver pelo menos duas colunas e a chave não estiver vazia
                    key = row[0]
                    value = row[1] if len(row) > 1 and row[1] else ""
                    config[key] = value
                    logger.info(f"Configuração carregada: {key} = {value}")
            
            logger.info(f"Configurações carregadas com sucesso: {json.dumps(config, ensure_ascii=False)}")
            return config
        except Exception as e:
            logger.warning(f"Erro ao acessar aba Config: {str(e)}. Usando configurações padrão.")
            return {}
    except Exception as e:
        logger.error(f"Erro ao obter configurações: {str(e)}")
        logger.error(traceback.format_exc())
        return {}

def save_form_data(form_data):
    """Save form data to Google Sheets"""
    try:
        logger.info("Iniciando salvamento de dados do formulário")
        client = get_sheet_client()
        
        # Usar ID direto em vez do nome da planilha
        SPREADSHEET_ID = "1UvH63UVLS8KkQJIh6y9hOvygOv2H6GWGZvKTAKMKFzc"
        logger.info(f"Tentando abrir a planilha com ID: {SPREADSHEET_ID}")
        
        sheet = client.open_by_key(SPREADSHEET_ID)
        
        try:
            logger.info("Tentando acessar a aba 'Respostas do Formulário 2'")
            form_sheet = sheet.worksheet("Respostas do Formulário 2")
        except gspread.exceptions.WorksheetNotFound:
            # Se a aba não existir, tenta Respostas do Formulário 1
            logger.info("Aba 'Respostas do Formulário 2' não encontrada. Tentando 'Respostas do Formulário 1'")
            try:
                form_sheet = sheet.worksheet("Respostas do Formulário 1")
            except gspread.exceptions.WorksheetNotFound:
                # Se ainda não existir, tenta Sheet1 ou cria nova
                logger.info("Tentando acessar a primeira aba ou criar nova aba")
                try:
                    form_sheet = sheet.get_worksheet(0)  # Primeira aba
                except:
                    form_sheet = sheet.add_worksheet(title="Respostas do Formulário", rows=1000, cols=50)
        
        # Define os cabeçalhos exatos da planilha existente
        expected_headers = [
            'Carimbo de data/hora',
            'Nome completo:',
            'Email de contacto:',
            'Número de telefone:',
            'Morada completa:',
            'Data de nascimento:',
            'Tem carta de condução válida?',
            'Tem experiência com cuidados a idosos e/ou pessoas dependentes?',
            'Se sim, tipo de experiência:',
            'Duração total da experiência:',
            'Funções desempenhadas:',
            'É cidadão português?',
            'Se não, está legalmente autorizado(a) a trabalhar em Portugal?',
            'Documento que possui:',
            'Há quanto tempo está em Portugal?',
            'Disponibilidade para trabalhar como prestador de serviços (recibos verdes)?',
            'Tem formação na área da saúde/cuidados a idosos?',
            'Tipo de formação:',
            'Nome da entidade formadora:',
            'Ano de conclusão:',
            'Dias disponíveis para trabalhar:',
            'Turnos disponíveis:',
            'Carregue aqui o seu CV',
            'Zona de residência atual:',
            'Endereço de email',
            'Erro: Link CV ausente ou inválido',
            'STATUS',
            'Classificacao IA',
            'Justificacao IA',
            'Horarios Sugeridos',
            'Email Enviado',
            'Provedor IA'
        ]
        
        # Verificar se já existem cabeçalhos
        logger.info("Verificando cabeçalhos existentes")
        headers = form_sheet.row_values(1)
        logger.info(f"Cabeçalhos encontrados: {headers}")
        
        # Se não existem cabeçalhos, adiciona-os
        if not headers:
            logger.info("Nenhum cabeçalho encontrado. Adicionando cabeçalhos.")
            form_sheet.append_row(expected_headers)
        
        # Prepare row data - usando os índices dos cabeçalhos esperados
        logger.info("Preparando dados da linha para inserção")
        row_data = [""] * len(expected_headers)
        
        # Preencher os dados nas posições corretas
        row_data[0] = form_data.get('data', '')                                    # Carimbo de data/hora
        row_data[1] = form_data.get('nome', '')                                    # Nome completo:
        row_data[2] = form_data.get('email', '')                                   # Email de contacto:
        row_data[3] = form_data.get('telefone', '')                                # Número de telefone:
        row_data[4] = form_data.get('morada', '')                                  # Morada completa:
        row_data[5] = form_data.get('data_nascimento', '')                         # Data de nascimento:
        row_data[6] = form_data.get('carta_conducao', '')                          # Tem carta de condução válida?
        row_data[7] = form_data.get('experiencia', '')                             # Tem experiência com cuidados a idosos e/ou pessoas dependentes?
        row_data[8] = form_data.get('tipo_experiencia', '')                        # Se sim, tipo de experiência:
        row_data[9] = form_data.get('duracao_experiencia', '')                     # Duração total da experiência:
        row_data[10] = form_data.get('funcoes', '')                                # Funções desempenhadas:
        row_data[11] = form_data.get('cidadao_portugues', '')                      # É cidadão português?
        row_data[12] = form_data.get('autorizacao_portugal', '')                   # Se não, está legalmente autorizado(a) a trabalhar em Portugal?
        row_data[13] = form_data.get('documento', '')                              # Documento que possui:
        row_data[14] = form_data.get('tempo_portugal', '')                         # Há quanto tempo está em Portugal?
        row_data[15] = form_data.get('recibos_verdes', '')                         # Disponibilidade para trabalhar como prestador de serviços (recibos verdes)?
        row_data[16] = form_data.get('formacao_area', '')                          # Tem formação na área da saúde/cuidados a idosos?
        row_data[17] = form_data.get('tipo_formacao', '')                          # Tipo de formação:
        row_data[18] = form_data.get('entidade_formadora', '')                     # Nome da entidade formadora:
        row_data[19] = form_data.get('ano_conclusao', '')                          # Ano de conclusão:
        row_data[20] = form_data.get('dias_disponiveis', '')                       # Dias disponíveis para trabalhar:
        row_data[21] = form_data.get('turnos_disponiveis', '')                     # Turnos disponíveis:
        row_data[22] = "Enviado pelo formulário web"                               # Carregue aqui o seu CV
        row_data[23] = form_data.get('residencia', '')                             # Zona de residência atual:
        row_data[24] = form_data.get('email', '')                                  # Endereço de email
        row_data[25] = ""                                                          # Erro: Link CV ausente ou inválido
        row_data[26] = "NOVO"                                                      # STATUS
        row_data[27] = form_data.get('classificacao', '')                          # Classificacao IA
        row_data[28] = form_data.get('justificacao', '')                           # Justificacao IA
        row_data[29] = ""                                                          # Horarios Sugeridos
        row_data[30] = "Não"                                                       # Email Enviado
        
        # Adicionando provedor de IA se presente
        if 'provider' in form_data:
            # Verificar se já existe coluna para o provedor de IA
            provider_col = None
            for i, header in enumerate(expected_headers):
                if header == 'Provedor IA':
                    provider_col = i
                    break
            
            # Se a coluna existir, preencher o valor
            if provider_col is not None:
                row_data[provider_col] = form_data.get('provider', '')
            # Se não existir, adicionar nova coluna
            else:
                expected_headers.append('Provedor IA')
                row_data.append(form_data.get('provider', ''))
                # Atualizar cabeçalhos na planilha
                form_sheet.append_row(expected_headers, table_range='A1')
        
        # Atualizar o Link do CV na coluna apropriada
        if form_data.get('cv_url'):
            logger.info(f"Adicionando URL do CV: {form_data.get('cv_url')}")
            # Não há coluna específica para o link do CV, mas poderíamos adicionar na coluna de erros ou outra
            row_data[25] = form_data.get('cv_url', '')                            # Usamos a coluna de erro para o link
        
        # Append the row to the sheet
        logger.info("Adicionando linha à planilha")
        form_sheet.append_row(row_data)
        logger.info("Dados salvos com sucesso na planilha")
        
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar dados do formulário: {str(e)}")
        logger.error(traceback.format_exc())
        raise

def get_available_slots(days_ahead=7):
    """
    Get available interview slots from the Horarios sheet
    for the next 'days_ahead' days (default: 7 days)
    """
    try:
        logger.info(f"Buscando horários disponíveis para os próximos {days_ahead} dias")
        client = get_sheet_client()
        
        # Usar ID direto em vez do nome da planilha
        SPREADSHEET_ID = "1UvH63UVLS8KkQJIh6y9hOvygOv2H6GWGZvKTAKMKFzc"
        logger.info(f"Tentando abrir a planilha com ID: {SPREADSHEET_ID}")
        
        sheet = client.open_by_key(SPREADSHEET_ID)
        
        try:
            logger.info("Tentando acessar a aba 'Horarios'")
            horarios_sheet = sheet.worksheet("Horarios")
        except gspread.exceptions.WorksheetNotFound:
            logger.warning("Aba 'Horarios' não encontrada. Criando aba.")
            horarios_sheet = sheet.add_worksheet(title="Horarios", rows=100, cols=10)
            # Adicionar cabeçalhos
            horarios_sheet.append_row(["Dia da Semana", "Início", "Fim", "Entrevistador", "Candidato", "Status"])
            logger.info("Aba 'Horarios' criada com sucesso.")
        
        # Get all records from Horarios sheet
        logger.info("Lendo registros da aba Horarios")
        records = horarios_sheet.get_all_records()
        logger.info(f"Encontrados {len(records)} registros de horários")
        
        # Get interview duration from Config
        logger.info("Obtendo duração da entrevista das configurações")
        config = get_config()
        interview_duration = int(config.get('DURACAO_ENTREVISTA_MIN', 30))
        logger.info(f"Duração da entrevista configurada: {interview_duration} minutos")
        
        # Get current date and time
        current_date = datetime.datetime.now()
        logger.info(f"Data atual: {current_date}")
        
        # Calculate the end date for our search
        end_date = current_date + datetime.timedelta(days=days_ahead)
        logger.info(f"Data final para busca de horários: {end_date}")
        
        # List of weekdays in Portuguese
        weekdays_pt = {
            0: "Segunda-feira",
            1: "Terça-feira",
            2: "Quarta-feira",
            3: "Quinta-feira",
            4: "Sexta-feira",
            5: "Sábado",
            6: "Domingo"
        }
        
        # Find available slots
        available_slots = []
        
        for day_offset in range(days_ahead):
            check_date = current_date + datetime.timedelta(days=day_offset)
            weekday_name = weekdays_pt[check_date.weekday()]
            logger.info(f"Verificando horários para {weekday_name} ({check_date.strftime('%d/%m/%Y')})")
            
            # Filter records for this weekday
            # Ajustado para usar os nomes de colunas da sua planilha
            day_slots = [r for r in records if r['Dia da Semana'] == weekday_name and not r.get('Entrevistador')]
            logger.info(f"Encontrados {len(day_slots)} horários disponíveis para {weekday_name}")
            
            for slot in day_slots:
                # Usando os nomes de colunas da sua planilha
                start_time = slot['Início']
                end_time = slot['Fim']
                logger.info(f"Horário disponível: {start_time} - {end_time}")
                
                # Format date and time information for this slot
                slot_date = check_date.strftime("%d/%m/%Y")
                available_slots.append({
                    'date': slot_date,
                    'weekday': weekday_name,
                    'start_time': start_time,
                    'end_time': end_time
                })
                
                # Limit to 3 slots
                if len(available_slots) >= 3:
                    logger.info(f"Limite de 3 horários atingido. Retornando {len(available_slots)} horários.")
                    return available_slots
        
        logger.info(f"Retornando {len(available_slots)} horários disponíveis")
        return available_slots
    except Exception as e:
        logger.error(f"Erro ao obter horários disponíveis: {str(e)}")
        logger.error(traceback.format_exc())
        return [] 

def get_all_candidates():
    """
    Obtém todos os candidatos da planilha
    Retorna uma lista de dicionários com os dados de cada candidato
    """
    try:
        logger.info("Buscando todos os candidatos...")
        client = get_sheet_client()
        
        # Usar ID direto em vez do nome da planilha
        SPREADSHEET_ID = "1UvH63UVLS8KkQJIh6y9hOvygOv2H6GWGZvKTAKMKFzc"
        logger.info(f"Tentando abrir a planilha com ID: {SPREADSHEET_ID}")
        
        sheet = client.open_by_key(SPREADSHEET_ID)
        
        try:
            logger.info("Tentando acessar a aba 'Respostas do Formulário 2'")
            form_sheet = sheet.worksheet("Respostas do Formulário 2")
        except gspread.exceptions.WorksheetNotFound:
            # Se a aba não existir, tenta Respostas do Formulário 1
            logger.info("Aba 'Respostas do Formulário 2' não encontrada. Tentando 'Respostas do Formulário 1'")
            try:
                form_sheet = sheet.worksheet("Respostas do Formulário 1")
            except gspread.exceptions.WorksheetNotFound:
                # Se ainda não existir, tenta a primeira aba
                logger.info("Tentando acessar a primeira aba")
                form_sheet = sheet.get_worksheet(0)  # Primeira aba
        
        # Obter todas as linhas da planilha
        logger.info("Lendo todas as entradas da planilha")
        all_records = form_sheet.get_all_records()
        
        # Retornar a lista de candidatos com o índice
        candidatos = []
        for i, record in enumerate(all_records, start=2):  # Começa em 2 pois a linha 1 é o cabeçalho
            candidato = record.copy()
            candidato['index'] = i
            candidatos.append(candidato)
        
        logger.info(f"Total de {len(candidatos)} candidatos encontrados")
        return candidatos
        
    except Exception as e:
        logger.error(f"Erro ao buscar candidatos: {str(e)}")
        logger.error(traceback.format_exc())
        return []

def get_candidate_by_index(row_index):
    """
    Obtém dados de um candidato específico pelo índice da linha
    Retorna um dicionário com os dados do candidato
    """
    try:
        logger.info(f"Buscando candidato na linha {row_index}")
        client = get_sheet_client()
        
        # Usar ID direto em vez do nome da planilha
        SPREADSHEET_ID = "1UvH63UVLS8KkQJIh6y9hOvygOv2H6GWGZvKTAKMKFzc"
        sheet = client.open_by_key(SPREADSHEET_ID)
        
        # Tenta encontrar a aba correta
        try:
            form_sheet = sheet.worksheet("Respostas do Formulário 2")
        except gspread.exceptions.WorksheetNotFound:
            try:
                form_sheet = sheet.worksheet("Respostas do Formulário 1")
            except gspread.exceptions.WorksheetNotFound:
                form_sheet = sheet.get_worksheet(0)
        
        # Obter cabeçalhos
        headers = form_sheet.row_values(1)
        
        # Obter valores da linha do candidato
        values = form_sheet.row_values(row_index)
        
        # Se não tiver valores suficientes, retorna None
        if not values:
            logger.warning(f"Nenhum dado encontrado na linha {row_index}")
            return None
        
        # Construir dicionário do candidato
        candidato = {}
        for i, header in enumerate(headers):
            if i < len(values):
                candidato[header] = values[i]
            else:
                candidato[header] = ""
        
        # Mapear para os campos usados na aplicação
        form_data = {}
        form_data['index'] = row_index
        form_data['nome'] = candidato.get('Nome completo:', '')
        form_data['email'] = candidato.get('Email de contacto:', '') or candidato.get('Endereço de email', '')
        form_data['telefone'] = candidato.get('Número de telefone:', '')
        form_data['morada'] = candidato.get('Morada completa:', '')
        form_data['data_nascimento'] = candidato.get('Data de nascimento:', '')
        form_data['cv_url'] = candidato.get('Erro: Link CV ausente ou inválido', '')
        form_data['classificacao'] = candidato.get('Classificacao IA', '')
        form_data['justificacao'] = candidato.get('Justificacao IA', '')
        form_data['status'] = candidato.get('STATUS', '')
        
        # Verificar se tem dados básicos
        if not form_data['nome'] or not form_data['email']:
            logger.warning(f"Dados incompletos para o candidato na linha {row_index}")
        
        logger.info(f"Candidato encontrado: {form_data['nome']}")
        return form_data
        
    except Exception as e:
        logger.error(f"Erro ao buscar candidato na linha {row_index}: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def update_candidate_analysis(row_index, cv_analysis):
    """
    Atualiza a análise de um candidato na planilha
    """
    try:
        logger.info(f"Atualizando análise para candidato na linha {row_index}")
        client = get_sheet_client()
        
        # Usar ID direto em vez do nome da planilha
        SPREADSHEET_ID = "1UvH63UVLS8KkQJIh6y9hOvygOv2H6GWGZvKTAKMKFzc"
        sheet = client.open_by_key(SPREADSHEET_ID)
        
        # Tenta encontrar a aba correta
        try:
            form_sheet = sheet.worksheet("Respostas do Formulário 2")
        except gspread.exceptions.WorksheetNotFound:
            try:
                form_sheet = sheet.worksheet("Respostas do Formulário 1")
            except gspread.exceptions.WorksheetNotFound:
                form_sheet = sheet.get_worksheet(0)
        
        # Obter cabeçalhos para encontrar as colunas corretas
        headers = form_sheet.row_values(1)
        
        # Encontrar índices das colunas
        classificacao_col = None
        justificacao_col = None
        status_col = None
        provider_col = None
        
        for i, header in enumerate(headers, start=1):
            if header == 'Classificacao IA':
                classificacao_col = i
            elif header == 'Justificacao IA':
                justificacao_col = i
            elif header == 'STATUS':
                status_col = i
            elif header == 'Provedor IA':
                provider_col = i
        
        # Atualizar células
        if classificacao_col:
            form_sheet.update_cell(row_index, classificacao_col, cv_analysis.get('classificacao', 'Desconhecido'))
            logger.info(f"Classificação atualizada: {cv_analysis.get('classificacao', 'Desconhecido')}")
        
        if justificacao_col:
            form_sheet.update_cell(row_index, justificacao_col, cv_analysis.get('justificacao', ''))
            logger.info(f"Justificação atualizada")
        
        if status_col:
            # Atualizar o status com base na classificação
            classificacao = cv_analysis.get('classificacao', '')
            if classificacao == 'Aprovado':
                status = 'ANALISADO'
            elif classificacao == 'Rejeitado':
                status = 'REJEITADO'
            elif classificacao == 'Revisão':
                status = 'REVISÃO'
            else:
                status = 'NOVO'
            
            form_sheet.update_cell(row_index, status_col, status)
            logger.info(f"Status atualizado: {status}")
        
        # Atualizar o provedor de IA
        if 'provider' in cv_analysis:
            if provider_col:
                form_sheet.update_cell(row_index, provider_col, cv_analysis.get('provider', ''))
                logger.info(f"Provedor IA atualizado: {cv_analysis.get('provider', '')}")
            else:
                # Adicionar nova coluna para o provedor se não existir
                headers.append('Provedor IA')
                form_sheet.update_cell(1, len(headers), 'Provedor IA')
                form_sheet.update_cell(row_index, len(headers), cv_analysis.get('provider', ''))
                logger.info(f"Coluna de Provedor IA adicionada e valor atualizado: {cv_analysis.get('provider', '')}")
        
        logger.info(f"Análise atualizada com sucesso para o candidato na linha {row_index}")
        return True
    
    except Exception as e:
        logger.error(f"Erro ao atualizar análise: {str(e)}")
        logger.error(traceback.format_exc())
        return False 

def update_config(config_updates):
    """
    Atualiza as configurações na planilha
    config_updates: dicionário com as configurações a atualizar
    """
    try:
        logger.info(f"Atualizando configurações: {json.dumps(config_updates, ensure_ascii=False)}")
        client = get_sheet_client()
        
        # Usar ID direto em vez do nome da planilha
        SPREADSHEET_ID = "1UvH63UVLS8KkQJIh6y9hOvygOv2H6GWGZvKTAKMKFzc"
        sheet = client.open_by_key(SPREADSHEET_ID)
        
        # Verificar se a aba Config existe, caso contrário, criar
        try:
            config_sheet = sheet.worksheet("Config")
            logger.info("Aba Config encontrada")
        except gspread.exceptions.WorksheetNotFound:
            logger.info("Aba Config não encontrada. Criando nova aba.")
            config_sheet = sheet.add_worksheet(title="Config", rows=50, cols=2)
            # Adicionar cabeçalhos
            config_sheet.append_row(["CHAVE", "VALOR"])
        
        # Obter todos os dados da planilha, incluindo os valores das células
        all_values = config_sheet.get_all_values()
        if not all_values:
            # Planilha vazia, adicionar cabeçalhos
            config_sheet.append_row(["CHAVE", "VALOR"])
            all_values = [["CHAVE", "VALOR"]]
        
        # Criar um mapeamento de chaves para índices de linha
        key_to_row = {}
        for i, row in enumerate(all_values):
            if i == 0:  # Pular o cabeçalho
                continue
            if len(row) >= 1:
                key_to_row[row[0]] = i + 1  # +1 porque a linha 1 é o cabeçalho
        
        # Atualizar valores existentes e adicionar novos
        updates_made = 0
        
        for key, value in config_updates.items():
            if key in key_to_row:
                # Atualizar valor existente
                row_idx = key_to_row[key]
                logger.info(f"Atualizando configuração existente: {key}={value} na linha {row_idx}")
                config_sheet.update_cell(row_idx, 2, value)  # Coluna 2 = VALOR
                updates_made += 1
            else:
                # Adicionar nova configuração
                logger.info(f"Adicionando nova configuração: {key}={value}")
                config_sheet.append_row([key, value])
                updates_made += 1
        
        logger.info(f"Total de {updates_made} configurações atualizadas")
        return True
    
    except Exception as e:
        logger.error(f"Erro ao atualizar configurações: {str(e)}")
        logger.error(traceback.format_exc())
        return False 

def get_custom_prompt():
    """
    Obtém a prompt personalizada para análise de CV da aba Prompt da planilha
    Retorna None se a aba não existir ou se não houver prompt definida
    """
    try:
        logger.info("Tentando obter prompt personalizada da planilha...")
        client = get_sheet_client()
        
        # Usar ID direto em vez do nome da planilha
        SPREADSHEET_ID = "1UvH63UVLS8KkQJIh6y9hOvygOv2H6GWGZvKTAKMKFzc"
        sheet = client.open_by_key(SPREADSHEET_ID)
        
        # Verificar se a aba Prompt existe
        try:
            prompt_sheet = sheet.worksheet("Prompt")
            logger.info("Aba Prompt encontrada")
        except gspread.exceptions.WorksheetNotFound:
            # Se a aba não existir, criar nova com um template de prompt
            logger.info("Aba Prompt não encontrada. Criando nova aba com template de prompt.")
            prompt_sheet = sheet.add_worksheet(title="Prompt", rows=50, cols=1)
            
            # Template de prompt padrão
            default_prompt = """
Analise o currículo abaixo para o candidato {nome} que está se aplicando para a vaga de {cargo}.

Detalhes do candidato:
- Nome: {nome}
- Email: {email}
- Telefone: {telefone}
- Cargo pretendido: {cargo}

Respostas completas do formulário:
{respostas}

Currículo:
{text}

Responda às seguintes perguntas:
1. Quais são as principais habilidades e competências do candidato?
2. O candidato tem experiência relevante para a vaga de {cargo}? Liste as experiências relevantes.
3. O candidato tem formação adequada para a vaga? Descreva a formação.
4. Quais são os pontos fortes do candidato que o tornam adequado para esta posição?
5. Há alguma lacuna ou ponto de atenção no perfil do candidato?
6. Em uma escala de 0 a 10, qual seria a pontuação deste candidato para a vaga, considerando o alinhamento do perfil?
7. O candidato deve ser chamado para entrevista? Por quê?

Forneça uma análise detalhada e objetiva baseada apenas nas informações do currículo.
"""
            # Adicionar o template à célula A1
            prompt_sheet.update_cell(1, 1, default_prompt)
            logger.info("Template de prompt adicionado à aba Prompt")
        
        # Ler o conteúdo da célula A1
        prompt_text = prompt_sheet.cell(1, 1).value
        
        if not prompt_text:
            logger.warning("Prompt não encontrada ou vazia na célula A1 da aba Prompt")
            return None
        
        logger.info("Prompt personalizada obtida com sucesso")
        return prompt_text
    
    except Exception as e:
        logger.error(f"Erro ao obter prompt personalizada: {str(e)}")
        logger.error(traceback.format_exc())
        return None 
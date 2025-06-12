from flask import Flask, render_template, request, flash, redirect, url_for, jsonify, abort
import os
from werkzeug.utils import secure_filename
import datetime
import json
import logging
import traceback
import sys
import tempfile
import re

from utils.sheets import get_config, save_form_data, get_available_slots, get_candidate_by_index, get_all_candidates, update_candidate_analysis, update_config
from utils.drive import upload_file_to_drive, download_cv_for_processing, download_file_from_drive
from utils.ia import analyze_cv
from utils.mail import send_email
from utils.api_checker import check_api_status

# Get current directory
current_dir = os.path.dirname(os.path.abspath(__file__))

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Reduzir o ruído de bibliotecas externas
logging.getLogger("pdfminer").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("google").setLevel(logging.WARNING)
logging.getLogger("werkzeug").setLevel(logging.WARNING)

logger = logging.getLogger('formulario_culsen')

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configurar pasta de upload
UPLOAD_FOLDER = os.path.join(current_dir, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Configurar pasta temp
TEMP_FOLDER = os.path.join(current_dir, 'temp')
os.makedirs(TEMP_FOLDER, exist_ok=True)

# Extensões permitidas
ALLOWED_EXTENSIONS = {'pdf', 'txt', 'doc', 'docx'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

def allowed_file(filename):
    """Check if file has an allowed extension"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_drive_id(url):
    """Extract Google Drive file ID from URL"""
    if not url:
        return None
    
    # Padrões comuns de URLs do Google Drive
    patterns = [
        r'https://drive\.google\.com/file/d/([a-zA-Z0-9_-]+)',
        r'https://drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)',
        r'https://docs\.google\.com/document/d/([a-zA-Z0-9_-]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

def download_cv_for_processing(cv_url, temp_filename):
    """Download CV from Google Drive URL and return local file path"""
    try:
        logger.info(f"Fazendo download do CV: {cv_url}")
        
        # Extrair ID do arquivo
        file_id = extract_drive_id(cv_url)
        if not file_id:
            logger.error(f"ID do arquivo extraído: {file_id}")
            return None
        
        logger.info(f"ID do arquivo extraído: {file_id}")
        
        # Criar diretório temp se não existir
        temp_dir = os.path.join(current_dir, 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        # Caminho para salvar o arquivo temporário
        temp_file_path = os.path.join(temp_dir, temp_filename)
        
        # Baixar o arquivo do Google Drive
        success = download_file_from_drive(file_id, temp_file_path)
        
        if success:
            logger.info(f"Download concluído: {temp_file_path}")
            return temp_file_path
        else:
            logger.error("Falha ao baixar arquivo do Google Drive")
            return None
        
    except Exception as e:
        logger.error(f"Erro ao baixar CV: {str(e)}")
        logger.error(traceback.format_exc())
        return None

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        logger.info("Recebido POST na rota principal")
        
        # Check if all required fields are present
        required_fields = ['nome', 'email', 'telefone', 'morada', 'data_nascimento', 
                          'autorizacao_portugal', 'recibos_verdes', 'formacao', 'residencia']
                          
        for field in required_fields:
            if not request.form.get(field):
                logger.warning(f"Campo obrigatório ausente: {field}")
                flash(f'Por favor preencha o campo {field}', 'danger')
                return redirect(url_for('index'))
        
        logger.info("Todos os campos obrigatórios estão presentes")
        
        # Check if file was uploaded
        if 'cv' not in request.files:
            logger.warning("Nenhum arquivo CV foi enviado")
            flash('Nenhum ficheiro CV enviado', 'danger')
            return redirect(url_for('index'))
            
        file = request.files['cv']
        
        if file.filename == '':
            logger.warning("Nome do arquivo CV está vazio")
            flash('Nenhum ficheiro CV selecionado', 'danger')
            return redirect(url_for('index'))
            
        if not allowed_file(file.filename):
            logger.warning(f"Formato de arquivo não permitido: {file.filename}")
            flash('Formato de ficheiro não permitido. Use PDF, TXT, DOC ou DOCX.', 'danger')
            return redirect(url_for('index'))
        
        logger.info(f"Arquivo CV válido: {file.filename}")
            
        # Save file temporarily
        filename = secure_filename(file.filename)
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(temp_path)
        logger.info(f"Arquivo salvo temporariamente em: {temp_path}")
        
        try:
            # Upload to Google Drive
            logger.info("Tentando fazer upload para o Google Drive...")
            file_url = upload_file_to_drive(temp_path, filename)
            logger.info(f"Upload concluído com sucesso. URL: {file_url}")
            
            # Processar campos do tipo multi-select (checkboxes)
            logger.info("Processando campos do tipo multi-select...")
            tipo_experiencia = request.form.getlist('tipo_experiencia[]')
            funcoes = request.form.getlist('funcoes[]')
            tipo_formacao = request.form.getlist('tipo_formacao[]')
            dias_disponiveis = request.form.getlist('dias_disponiveis[]')
            turnos_disponiveis = request.form.getlist('turnos_disponiveis[]')
            
            # Analyze CV with Gemini
            logger.info("Analisando CV com Gemini...")
            cv_analysis = analyze_cv(temp_path, request.form)
            logger.info(f"Análise do CV concluída: {cv_analysis}")
            
            # Extrair classificação baseada na análise
            analysis_text = cv_analysis.get('analysis', '')
            
            # Procurar pela pontuação na escala de 0 a 10
            score_match = re.search(r'Em uma escala de 0 a 10,\s*(?:.*?)(\d+(?:\.\d+)?)', analysis_text, re.IGNORECASE)
            score = float(score_match.group(1)) if score_match else 0
            
            # Procurar pela recomendação de entrevista
            interview_match = re.search(r'O candidato deve ser chamado para entrevista\?\s*(.*?)(?:\.|$)', analysis_text, re.IGNORECASE)
            interview_recommendation = interview_match.group(1) if interview_match else ""
            
            # Classificar candidato com base na pontuação
            if score >= 7:
                cv_analysis['classificacao'] = 'Aprovado'
            elif score >= 4:
                cv_analysis['classificacao'] = 'Revisão'
            else:
                cv_analysis['classificacao'] = 'Rejeitado'
            
            cv_analysis['justificacao'] = analysis_text
            
            # Save form data to Google Sheets
            logger.info("Preparando dados para salvar na planilha...")
            form_data = {
                'data': datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                'nome': request.form.get('nome'),
                'email': request.form.get('email'),
                'telefone': request.form.get('telefone'),
                'morada': request.form.get('morada'),
                'data_nascimento': request.form.get('data_nascimento'),
                'carta_conducao': request.form.get('carta_conducao'),
                'experiencia': request.form.get('experiencia'),
                'tipo_experiencia': json.dumps(tipo_experiencia) if tipo_experiencia else '',
                'duracao_experiencia': request.form.get('duracao_experiencia'),
                'funcoes': json.dumps(funcoes) if funcoes else '',
                'cidadao_portugues': request.form.get('cidadao_portugues'),
                'autorizacao_portugal': request.form.get('autorizacao_portugal'),
                'documento': request.form.get('documento'),
                'tempo_portugal': request.form.get('tempo_portugal'),
                'recibos_verdes': request.form.get('recibos_verdes'),
                'formacao_area': request.form.get('formacao_area'),
                'tipo_formacao': json.dumps(tipo_formacao) if tipo_formacao else '',
                'entidade_formadora': request.form.get('entidade_formadora'),
                'ano_conclusao': request.form.get('ano_conclusao'),
                'formacao': request.form.get('formacao'),
                'dias_disponiveis': json.dumps(dias_disponiveis) if dias_disponiveis else '',
                'turnos_disponiveis': json.dumps(turnos_disponiveis) if turnos_disponiveis else '',
                'residencia': request.form.get('residencia'),
                'cv_url': file_url,
                'classificacao': cv_analysis.get('classificacao', 'Desconhecido'),
                'justificacao': cv_analysis.get('justificacao', ''),
                'provider': cv_analysis.get('provider', 'Desconhecido')
            }
            
            logger.info("Salvando dados do formulário na planilha...")
            save_form_data(form_data)
            logger.info("Dados salvos com sucesso")
            
            # If candidate is approved, send email with available slots
            if cv_analysis.get('classificacao') == 'Aprovado':
                logger.info("Candidato aprovado. Buscando horários disponíveis...")
                available_slots = get_available_slots()
                
                if available_slots:
                    logger.info(f"Encontrados {len(available_slots)} horários disponíveis. Enviando email...")
                    send_email(form_data['email'], form_data['nome'], available_slots)
                    logger.info("Email enviado com sucesso")
                    flash('Candidatura submetida com sucesso! Verifique o seu email.', 'success')
                else:
                    logger.warning("Não há horários disponíveis para o candidato")
                    flash('Candidatura aprovada, mas não há horários disponíveis.', 'warning')
            else:
                logger.info("Candidato não aprovado automaticamente")
                flash('Candidatura submetida com sucesso!', 'success')
                
            # Clean up temp file
            logger.info(f"Limpando arquivo temporário: {temp_path}")
            os.remove(temp_path)
            
            return redirect(url_for('index'))
        
        except Exception as e:
            logger.error(f"Erro ao processar candidatura: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Clean up temp file
            if os.path.exists(temp_path):
                logger.info(f"Limpando arquivo temporário após erro: {temp_path}")
                os.remove(temp_path)
                
            flash(f'Erro ao processar candidatura: {str(e)}', 'danger')
            return redirect(url_for('index'))
    
    return render_template('form.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    """Interface de administração para gerenciar candidaturas"""
    if request.method == 'POST':
        # Verificar se é um pedido para reprocessar uma candidatura
        if 'reprocess' in request.form:
            row_index = int(request.form.get('row_index'))
            logger.info(f"Reprocessando candidatura na linha {row_index}")
            
            try:
                # Buscar dados da candidatura
                candidato_data = get_candidate_by_index(row_index)
                if not candidato_data:
                    flash('Candidatura não encontrada', 'danger')
                    return redirect(url_for('admin'))
                
                # Verificar se tem CV
                cv_url = candidato_data.get('cv_url')
                if not cv_url:
                    flash('CV não encontrado para esta candidatura', 'danger')
                    return redirect(url_for('admin'))
                
                # Download do CV
                cv_path = download_cv_for_processing(cv_url, f"temp_cv_{row_index}.pdf")
                
                # Reprocessar com Gemini
                logger.info(f"Reprocessando CV: {cv_path}")
                cv_analysis = analyze_cv(cv_path, candidato_data)
                logger.info(f"Análise do CV concluída: {cv_analysis}")
                
                # Extrair classificação baseada na análise
                analysis_text = cv_analysis.get('analysis', '')
                
                # Procurar pela pontuação na escala de 0 a 10
                score_match = re.search(r'Em uma escala de 0 a 10,\s*(?:.*?)(\d+(?:\.\d+)?)', analysis_text, re.IGNORECASE)
                score = float(score_match.group(1)) if score_match else 0
                
                # Procurar pela recomendação de entrevista
                interview_match = re.search(r'O candidato deve ser chamado para entrevista\?\s*(.*?)(?:\.|$)', analysis_text, re.IGNORECASE)
                interview_recommendation = interview_match.group(1) if interview_match else ""
                
                # Classificar candidato com base na pontuação
                if score >= 7:
                    cv_analysis['classificacao'] = 'Aprovado'
                elif score >= 4:
                    cv_analysis['classificacao'] = 'Revisão'
                else:
                    cv_analysis['classificacao'] = 'Rejeitado'
                
                cv_analysis['justificacao'] = analysis_text
                
                # Atualizar dados na planilha
                update_candidate_analysis(row_index, cv_analysis)
                
                # Limpar arquivo temporário
                if os.path.exists(cv_path):
                    os.remove(cv_path)
                
                flash('Candidatura reprocessada com sucesso!', 'success')
                
            except Exception as e:
                logger.error(f"Erro ao reprocessar candidatura: {str(e)}")
                logger.error(traceback.format_exc())
                flash(f'Erro ao reprocessar candidatura: {str(e)}', 'danger')
            
            return redirect(url_for('admin'))
    
    # Buscar todas as candidaturas e configurações
    try:
        candidatos = get_all_candidates()
        config = get_config()
        
        # Verificar status das APIs
        api_status = check_api_status()
        
        return render_template('admin.html', candidatos=candidatos, config=config, api_status=api_status)
    except Exception as e:
        logger.error(f"Erro ao carregar candidaturas: {str(e)}")
        logger.error(traceback.format_exc())
        flash(f'Erro ao carregar candidaturas: {str(e)}', 'danger')
        return render_template('admin.html', candidatos=[], config={}, api_status={})

@app.route('/admin/candidate/<int:index>')
def admin_candidate(index):
    try:
        logger.info(f"Visualizando candidato com índice {index}")
        
        # Obter dados do candidato
        candidato = get_candidate_by_index(index)
        
        if not candidato:
            logger.error(f"Candidato não encontrado: {index}")
            flash("Candidato não encontrado", "danger")
            return redirect(url_for('admin'))
        
        return render_template('admin/candidate.html', candidato=candidato)
    
    except Exception as e:
        logger.error(f"Erro ao visualizar candidato: {str(e)}")
        logger.error(traceback.format_exc())
        flash(f"Erro ao carregar dados do candidato: {str(e)}", "danger")
        return redirect(url_for('admin'))

@app.route('/admin/reanalyze/<int:index>')
def admin_reanalyze(index):
    try:
        logger.info(f"Solicitando reanálise do candidato com índice {index}")
        
        # Obter dados do candidato
        candidato = get_candidate_by_index(index)
        
        if not candidato:
            logger.error(f"Candidato não encontrado: {index}")
            flash("Candidato não encontrado", "danger")
            return redirect(url_for('admin'))
        
        # Verificar se existe URL do CV
        cv_url = candidato.get('Carregue aqui o seu CV') or candidato.get('cv_url')
        if not cv_url:
            logger.error("URL do CV não encontrado para reanálise")
            flash("URL do CV não encontrado. Não é possível reanalisar.", "danger")
            return redirect(url_for('admin'))
        
        # Download do CV
        cv_path = download_cv_for_processing(cv_url, f"temp_cv_{index}.pdf")
        
        # Reprocessar com o provedor de IA atual
        logger.info(f"Reprocessando CV: {cv_path}")
        cv_analysis = analyze_cv(cv_path, candidato)
        logger.info(f"Análise do CV concluída: {cv_analysis}")
        
        # Extrair classificação baseada na análise
        analysis_text = cv_analysis.get('analysis', '')
        
        # Procurar pela pontuação na escala de 0 a 10
        score_match = re.search(r'Em uma escala de 0 a 10,\s*(?:.*?)(\d+(?:\.\d+)?)', analysis_text, re.IGNORECASE)
        score = float(score_match.group(1)) if score_match else 0
        
        # Procurar pela recomendação de entrevista
        interview_match = re.search(r'O candidato deve ser chamado para entrevista\?\s*(.*?)(?:\.|$)', analysis_text, re.IGNORECASE)
        interview_recommendation = interview_match.group(1) if interview_match else ""
        
        # Classificar candidato com base na pontuação
        if score >= 7:
            cv_analysis['classificacao'] = 'Aprovado'
        elif score >= 4:
            cv_analysis['classificacao'] = 'Revisão'
        else:
            cv_analysis['classificacao'] = 'Rejeitado'
        
        cv_analysis['justificacao'] = analysis_text
        
        # Atualizar dados na planilha
        success = update_candidate_analysis(index, cv_analysis)
        
        # Limpar arquivo temporário
        if os.path.exists(cv_path):
            os.remove(cv_path)
        
        if success:
            flash("Candidato reanalisado com sucesso!", "success")
        else:
            flash("Erro ao atualizar a análise na planilha", "danger")
        
        return redirect(url_for('admin'))
    
    except Exception as e:
        logger.error(f"Erro ao reanalisar candidato: {str(e)}")
        logger.error(traceback.format_exc())
        flash(f"Erro ao reanalisar candidato: {str(e)}", "danger")
        return redirect(url_for('admin'))

@app.route('/admin/config', methods=['POST'])
def admin_config():
    try:
        logger.info("Recebida solicitação para atualizar configurações")
        
        # Obter dados do formulário
        config_updates = {}
        
        # Processar cada campo do formulário de configuração
        for key in request.form:
            if request.form[key]:  # Apenas incluir campos não vazios
                config_updates[key] = request.form[key]
                logger.info(f"Configuração a ser atualizada: {key}={request.form[key]}")
        
        # Atualizar configurações na planilha
        result = update_config(config_updates)
        
        if result:
            flash("Configurações atualizadas com sucesso", "success")
            logger.info("Configurações atualizadas com sucesso")
        else:
            flash("Erro ao atualizar configurações", "danger")
            logger.error("Erro ao atualizar configurações")
        
        return redirect(url_for('admin'))
    
    except Exception as e:
        logger.error(f"Erro ao atualizar configurações: {str(e)}")
        logger.error(traceback.format_exc())
        flash(f"Erro ao atualizar configurações: {str(e)}", "danger")
        return redirect(url_for('admin'))

if __name__ == '__main__':
    logger.info("Iniciando a aplicação...")
    app.run(debug=True) 
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

from utils.sheets import get_config, save_form_data, save_dynamic_form_data, get_available_slots, get_candidate_by_index, get_all_candidates, update_candidate_analysis, update_config, get_dynamic_questions, get_active_forms, get_form_questions, save_form_configuration
from utils.file_cache import default_file_cache, auto_cleanup
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
    # Verificar formulários ativos
    try:
        active_forms = get_active_forms()
        logger.info(f"Encontrados {len(active_forms)} formulários ativos")
        
        # Se não há formulários ativos, mostrar mensagem
        if not active_forms:
            flash('Nenhum formulário está ativo no momento. Entre em contato com o administrador.', 'warning')
            return render_template('no_forms.html')
        
        # Se há apenas um formulário ativo, carregar diretamente
        if len(active_forms) == 1:
            form_id = active_forms[0]['ID']
            return redirect(url_for('form', form_id=form_id))
        
        # Se há múltiplos formulários, mostrar seleção
        return render_template('form_selection.html', forms=active_forms)
        
    except Exception as e:
        logger.error(f"Erro ao carregar formulários: {str(e)}")
        flash('Erro ao carregar formulários. Tente novamente mais tarde.', 'danger')
        return render_template('error.html')

@app.route('/form/<form_id>', methods=['GET', 'POST'])
def form(form_id):
    # Verificar se o formulário existe e está ativo
    try:
        active_forms = get_active_forms()
        current_form = None
        
        for form in active_forms:
            if form['ID'] == form_id:
                current_form = form
                break
        
        if not current_form:
            flash('Formulário não encontrado ou não está ativo.', 'danger')
            return redirect(url_for('index'))
        
        # Buscar perguntas do formulário
        dynamic_questions = get_form_questions(form_id)
        logger.info(f"Carregadas {len(dynamic_questions)} perguntas para o formulário {form_id}")
        
    except Exception as e:
        logger.error(f"Erro ao carregar formulário {form_id}: {str(e)}")
        dynamic_questions = []
        current_form = {'Nome': 'Formulário', 'Descricao': ''}
    
    if request.method == 'POST':
        logger.info("Recebido POST na rota principal")
        
        # Verificar campos obrigatórios baseados nas perguntas dinâmicas
        missing_fields = []
        for question in dynamic_questions:
            if question.get('Obrigatoria', '').lower() == 'sim':
                field_id = question['ID']
                if not request.form.get(field_id):
                    missing_fields.append(question['Pergunta'])
        
        if missing_fields:
            logger.warning(f"Campos obrigatórios ausentes: {missing_fields}")
            flash(f'Por favor preencha os seguintes campos obrigatórios: {", ".join(missing_fields)}', 'danger')
            return render_template('form_dynamic.html', questions=dynamic_questions)
        
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
            
            # Processar todos os campos do formulário dinâmico
            logger.info("Processando campos do formulário dinâmico...")
            processed_form_data = {}
            
            for question in dynamic_questions:
                field_id = question['ID']
                field_type = question['Tipo']
                
                if field_type == 'checkbox':
                    # Campos de múltipla escolha
                    values = request.form.getlist(f'{field_id}[]')
                    processed_form_data[f'{field_id}[]'] = values
                    processed_form_data[field_id] = json.dumps(values) if values else ''
                else:
                    # Campos simples
                    processed_form_data[field_id] = request.form.get(field_id, '')
            
            # Analyze CV with AI
            logger.info("Analisando CV com IA...")
            cv_analysis = analyze_cv(temp_path, processed_form_data)
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
            
            # Preparar dados para salvar na planilha
            logger.info("Preparando dados para salvar na planilha...")
            
            # Adicionar dados da análise de CV
            processed_form_data.update({
                'cv_url': file_url,
                'classificacao': cv_analysis.get('classificacao', 'Desconhecido'),
                'justificacao': cv_analysis.get('justificacao', ''),
                'provider': cv_analysis.get('provider', 'Desconhecido')
            })
            
            logger.info("Salvando dados do formulário dinâmico na planilha...")
            save_dynamic_form_data(processed_form_data, dynamic_questions)
            logger.info("Dados salvos com sucesso")
            
            # If candidate is approved, send email with available slots
            if cv_analysis.get('classificacao') == 'Aprovado':
                logger.info("Candidato aprovado. Buscando horários disponíveis...")
                available_slots = get_available_slots()
                
                if available_slots:
                    logger.info(f"Encontrados {len(available_slots)} horários disponíveis. Enviando email...")
                    candidate_email = processed_form_data.get('email', '')
                    candidate_name = processed_form_data.get('nome', '')
                    send_email(candidate_email, candidate_name, available_slots)
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
            
            return render_template('form_dynamic.html', questions=dynamic_questions)
        
        except Exception as e:
            logger.error(f"Erro ao processar candidatura: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Clean up temp file
            if os.path.exists(temp_path):
                logger.info(f"Limpando arquivo temporário após erro: {temp_path}")
                os.remove(temp_path)
                
            flash(f'Erro ao processar candidatura: {str(e)}', 'danger')
            return render_template('form_dynamic.html', questions=dynamic_questions, form=current_form)
    
    return render_template('form_dynamic.html', questions=dynamic_questions, form=current_form)

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

@app.route('/admin/cache/stats')
def admin_cache_stats():
    """Endpoint para visualizar estatísticas do cache"""
    try:
        stats = default_file_cache.get_stats()
        return jsonify({
            'success': True,
            'stats': stats,
            'cache_ttl_config': {
                'config_ttl': default_file_cache.ttl_config['config'],
                'candidates_ttl': default_file_cache.ttl_config['candidates'],
                'questions_ttl': default_file_cache.ttl_config['questions'],
                'forms_ttl': default_file_cache.ttl_config['forms'],
                'default_ttl': default_file_cache.default_ttl
            }
        })
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas do cache: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/cache/clear', methods=['POST'])
def admin_cache_clear():
    """Endpoint para limpar o cache"""
    try:
        removed_count = default_file_cache.clear()
        flash(f"Cache limpo com sucesso! {removed_count} arquivos removidos.", "success")
        logger.info(f"Cache limpo manualmente via admin: {removed_count} arquivos")
        return redirect(url_for('admin'))
    except Exception as e:
        logger.error(f"Erro ao limpar cache: {str(e)}")
        flash(f"Erro ao limpar cache: {str(e)}", "danger")
        return redirect(url_for('admin'))

@app.route('/admin/cache/refresh', methods=['POST'])
def admin_cache_refresh():
    """Endpoint para forçar refresh do cache"""
    try:
        # Forçar refresh das configurações e candidatos
        get_config(force_refresh=True)
        get_all_candidates(force_refresh=True)
        get_dynamic_questions(force_refresh=True)
        get_all_forms(force_refresh=True)
        
        flash("Cache atualizado com sucesso!", "success")
        logger.info("Cache atualizado manualmente via admin")
        return redirect(url_for('admin'))
    except Exception as e:
        logger.error(f"Erro ao atualizar cache: {str(e)}")
        flash(f"Erro ao atualizar cache: {str(e)}", "danger")
        return redirect(url_for('admin'))

@app.route('/admin/cache/cleanup', methods=['POST'])
def admin_cache_cleanup():
    """Endpoint para limpeza de caches expirados"""
    try:
        removed_count = default_file_cache.cleanup_expired()
        if removed_count > 0:
            flash(f"Limpeza concluída! {removed_count} caches expirados removidos.", "success")
        else:
            flash("Nenhum cache expirado encontrado.", "info")
        logger.info(f"Limpeza de cache executada: {removed_count} arquivos removidos")
        return redirect(url_for('admin'))
    except Exception as e:
        logger.error(f"Erro na limpeza de cache: {str(e)}")
        flash(f"Erro na limpeza de cache: {str(e)}", "danger")
        return redirect(url_for('admin'))

@app.route('/validate_cv', methods=['POST'])
def validate_cv():
    """Endpoint para validar se um arquivo é um currículo usando IA"""
    try:
        logger.info("Recebida solicitação de validação de CV")
        
        # Verificar se o arquivo foi enviado
        if 'file' not in request.files:
            return jsonify({'valid': False, 'message': 'Nenhum arquivo foi enviado'})
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'valid': False, 'message': 'Nenhum arquivo selecionado'})
        
        # Verificar extensão do arquivo
        if not allowed_file(file.filename):
            return jsonify({'valid': False, 'message': 'Formato de arquivo não permitido'})
        
        # Salvar arquivo temporariamente
        filename = secure_filename(file.filename)
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_validation_{filename}")
        file.save(temp_path)
        
        logger.info(f"Arquivo salvo temporariamente: {temp_path}")
        
        # Usar IA para validar se é um currículo
        from utils.ia import validate_cv_content
        
        validation_result = validate_cv_content(temp_path)
        
        # Limpar arquivo temporário
        if os.path.exists(temp_path):
            os.remove(temp_path)
            logger.info(f"Arquivo temporário removido: {temp_path}")
        
        logger.info(f"Resultado da validação: {validation_result}")
        
        return jsonify(validation_result)
        
    except Exception as e:
        logger.error(f"Erro ao validar CV: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Limpar arquivo temporário em caso de erro
        try:
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)
        except:
            pass
        
        return jsonify({'valid': False, 'message': f'Erro interno: {str(e)}'})

@app.route('/admin/questions')
def admin_questions():
    """Interface para gerenciar perguntas dinâmicas"""
    try:
        questions = get_dynamic_questions()
        return render_template('admin/questions.html', questions=questions)
    except Exception as e:
        logger.error(f"Erro ao carregar perguntas: {str(e)}")
        flash(f"Erro ao carregar perguntas: {str(e)}", "danger")
        return redirect(url_for('admin'))

@app.route('/admin/questions/preview')
def admin_questions_preview():
    """Preview do formulário com as perguntas atuais"""
    try:
        questions = get_dynamic_questions()
        return render_template('admin/questions_preview.html', questions=questions)
    except Exception as e:
        logger.error(f"Erro ao carregar preview: {str(e)}")
        flash(f"Erro ao carregar preview: {str(e)}", "danger")
        return redirect(url_for('admin_questions'))

@app.route('/admin/questions/edit', methods=['GET', 'POST'])
def admin_questions_edit():
    """Interface para editar perguntas do formulário"""
    if request.method == 'POST':
        try:
            # Processar dados do formulário
            questions_data = []
            
            # Obter dados das perguntas do formulário
            question_ids = request.form.getlist('question_id[]')
            sections = request.form.getlist('section[]')
            questions = request.form.getlist('question[]')
            types = request.form.getlist('type[]')
            required = request.form.getlist('required[]')
            options = request.form.getlist('options[]')
            placeholders = request.form.getlist('placeholder[]')
            helps = request.form.getlist('help[]')
            orders = request.form.getlist('order[]')
            actives = request.form.getlist('active[]')
            
            # Processar cada pergunta
            for i in range(len(question_ids)):
                if i < len(questions) and questions[i].strip():  # Só processar se tiver pergunta
                    question_data = [
                        question_ids[i] if i < len(question_ids) else f"q_{i+1}",
                        sections[i] if i < len(sections) else "Geral",
                        questions[i] if i < len(questions) else "",
                        types[i] if i < len(types) else "text",
                        "Sim" if f"required_{i}" in request.form else "Não",
                        options[i] if i < len(options) else "",
                        placeholders[i] if i < len(placeholders) else "",
                        helps[i] if i < len(helps) else "",
                        str(i + 1),  # Ordem baseada na posição
                        "Sim" if f"active_{i}" in request.form else "Não"
                    ]
                    questions_data.append(question_data)
            
            # Salvar no Google Sheets
            from utils.sheets import save_questions_to_sheet
            success = save_questions_to_sheet(questions_data)
            
            if success:
                # Invalidar cache
                default_file_cache.invalidate('questions_dynamic')
                flash('Perguntas atualizadas com sucesso!', 'success')
            else:
                flash('Erro ao salvar perguntas', 'danger')
                
        except Exception as e:
            logger.error(f"Erro ao salvar perguntas: {str(e)}")
            flash(f'Erro ao salvar perguntas: {str(e)}', 'danger')
        
        return redirect(url_for('admin_questions_edit'))
    
    # GET - Carregar perguntas existentes
    try:
        questions = get_dynamic_questions()
        # Incluir também perguntas inativas para edição
        from utils.sheets import get_all_questions
        all_questions = get_all_questions()
        return render_template('admin/questions_edit.html', questions=all_questions)
    except Exception as e:
        logger.error(f"Erro ao carregar perguntas para edição: {str(e)}")
        flash(f"Erro ao carregar perguntas: {str(e)}", "danger")
        return redirect(url_for('admin_questions'))

@app.route('/admin/questions/add', methods=['POST'])
def admin_questions_add():
    """Adicionar nova pergunta"""
    try:
        # Obter dados da nova pergunta
        question_data = {
            'id': request.form.get('id', ''),
            'section': request.form.get('section', ''),
            'question': request.form.get('question', ''),
            'type': request.form.get('type', 'text'),
            'required': 'Sim' if request.form.get('required') == 'on' else 'Não',
            'options': request.form.get('options', ''),
            'placeholder': request.form.get('placeholder', ''),
            'help': request.form.get('help', ''),
            'active': 'Sim' if request.form.get('active') == 'on' else 'Não'
        }
        
        # Adicionar à planilha
        from utils.sheets import add_question_to_sheet
        success = add_question_to_sheet(question_data)
        
        if success:
            default_file_cache.invalidate('questions_dynamic')
            flash('Pergunta adicionada com sucesso!', 'success')
        else:
            flash('Erro ao adicionar pergunta', 'danger')
            
    except Exception as e:
        logger.error(f"Erro ao adicionar pergunta: {str(e)}")
        flash(f'Erro ao adicionar pergunta: {str(e)}', 'danger')
    
    return redirect(url_for('admin_questions_edit'))

@app.route('/admin/questions/delete/<question_id>', methods=['POST'])
def admin_questions_delete(question_id):
    """Deletar pergunta"""
    try:
        from utils.sheets import delete_question_from_sheet
        success = delete_question_from_sheet(question_id)
        
        if success:
            default_file_cache.invalidate('questions_dynamic')
            flash('Pergunta removida com sucesso!', 'success')
        else:
            flash('Erro ao remover pergunta', 'danger')
            
    except Exception as e:
        logger.error(f"Erro ao deletar pergunta: {str(e)}")
        flash(f'Erro ao deletar pergunta: {str(e)}', 'danger')
    
    return redirect(url_for('admin_questions_edit'))

@app.route('/admin/forms')
def admin_forms():
    """Interface para gerenciar formulários"""
    try:
        from utils.sheets import get_all_forms
        forms = get_all_forms()
        return render_template('admin/forms.html', forms=forms)
    except Exception as e:
        logger.error(f"Erro ao carregar formulários: {str(e)}")
        flash(f"Erro ao carregar formulários: {str(e)}", "danger")
        return redirect(url_for('admin'))

@app.route('/admin/forms/new', methods=['GET', 'POST'])
def admin_forms_new():
    """Criar novo formulário"""
    if request.method == 'POST':
        try:
            form_data = {
                'ID': request.form.get('id', ''),
                'Nome': request.form.get('nome', ''),
                'Descricao': request.form.get('descricao', ''),
                'Ativo': 'Sim' if request.form.get('ativo') == 'on' else 'Não',
                'Categoria': request.form.get('categoria', 'Geral'),
                'Ordem': request.form.get('ordem', '1'),
                'Autor': 'Admin'
            }
            
            success = save_form_configuration(form_data)
            
            if success:
                flash('Formulário criado com sucesso!', 'success')
                return redirect(url_for('admin_forms'))
            else:
                flash('Erro ao criar formulário', 'danger')
                
        except Exception as e:
            logger.error(f"Erro ao criar formulário: {str(e)}")
            flash(f'Erro ao criar formulário: {str(e)}', 'danger')
    
    return render_template('admin/forms_new.html')

@app.route('/admin/forms/edit/<form_id>', methods=['GET', 'POST'])
def admin_forms_edit(form_id):
    """Editar formulário existente"""
    if request.method == 'POST':
        try:
            form_data = {
                'ID': form_id,
                'Nome': request.form.get('nome', ''),
                'Descricao': request.form.get('descricao', ''),
                'Ativo': 'Sim' if request.form.get('ativo') == 'on' else 'Não',
                'Categoria': request.form.get('categoria', 'Geral'),
                'Ordem': request.form.get('ordem', '1'),
                'Autor': 'Admin'
            }
            
            success = save_form_configuration(form_data)
            
            if success:
                flash('Formulário atualizado com sucesso!', 'success')
                return redirect(url_for('admin_forms'))
            else:
                flash('Erro ao atualizar formulário', 'danger')
                
        except Exception as e:
            logger.error(f"Erro ao atualizar formulário: {str(e)}")
            flash(f'Erro ao atualizar formulário: {str(e)}', 'danger')
    
    # GET - Carregar dados do formulário
    try:
        from utils.sheets import get_all_forms
        forms = get_all_forms()
        current_form = None
        
        for form in forms:
            if form['ID'] == form_id:
                current_form = form
                break
        
        if not current_form:
            flash('Formulário não encontrado', 'danger')
            return redirect(url_for('admin_forms'))
        
        return render_template('admin/forms_edit.html', form=current_form)
        
    except Exception as e:
        logger.error(f"Erro ao carregar formulário para edição: {str(e)}")
        flash(f"Erro ao carregar formulário: {str(e)}", "danger")
        return redirect(url_for('admin_forms'))

@app.route('/admin/forms/toggle/<form_id>', methods=['POST'])
def admin_forms_toggle(form_id):
    """Ativar/desativar formulário"""
    try:
        from utils.sheets import get_all_forms
        forms = get_all_forms()
        current_form = None
        
        for form in forms:
            if form['ID'] == form_id:
                current_form = form
                break
        
        if not current_form:
            flash('Formulário não encontrado', 'danger')
            return redirect(url_for('admin_forms'))
        
        # Alternar status
        new_status = 'Não' if current_form.get('Ativo', '').lower() == 'sim' else 'Sim'
        
        form_data = dict(current_form)
        form_data['Ativo'] = new_status
        
        success = save_form_configuration(form_data)
        
        if success:
            status_text = 'ativado' if new_status == 'Sim' else 'desativado'
            flash(f'Formulário {status_text} com sucesso!', 'success')
        else:
            flash('Erro ao alterar status do formulário', 'danger')
            
    except Exception as e:
        logger.error(f"Erro ao alterar status do formulário: {str(e)}")
        flash(f'Erro ao alterar status: {str(e)}', 'danger')
    
    return redirect(url_for('admin_forms'))

if __name__ == '__main__':
    logger.info("Iniciando a aplicação...")
    
    # Executar limpeza automática de cache na inicialização
    try:
        auto_cleanup()
        logger.info("Limpeza automática de cache executada na inicialização")
    except Exception as e:
        logger.warning(f"Erro na limpeza automática inicial: {str(e)}")
    
    app.run(debug=True) 
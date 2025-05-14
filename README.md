# Formulário Culsen

Sistema de recebimento e análise de currículos utilizando IA.

## Configuração Inicial

1. Clone este repositório
2. Configure as credenciais do Google:
   - Crie um projeto no [Google Cloud Console](https://console.cloud.google.com/)
   - Ative as APIs do Google Sheets e Google Drive
   - Baixe as credenciais JSON e salve como `formulario_culsen/credentials.json`
3. Configure a planilha Google Sheets:
   - Crie uma nova planilha no Google Sheets
   - O ID da planilha deve ser configurado no código (`SPREADSHEET_ID` em utils/sheets.py)
   - A planilha deve conter duas abas: "Formulario" e "Config"

## Instalação

Execute o script de instalação para instalar todas as dependências:

```bash
cd formulario_culsen
python install_dependencies.py
```

## Configuração da IA

O sistema suporta múltiplos provedores de IA para análise de currículos:

1. **Google Gemini** (padrão)
2. **OpenAI GPT**
3. **Anthropic Claude**
4. **DeepSeek**

### Configurando via Interface de Administração

1. Execute a aplicação com `python app.py`
2. Acesse a interface de administração pelo botão "Administração" no rodapé do formulário
3. Na seção "Configuração de IA", selecione o provedor desejado e insira a chave API
4. Clique em "Atualizar" para salvar as configurações

### Configurando Manualmente no Google Sheets

Na aba "Config" da planilha, adicione as seguintes configurações:

| CHAVE | VALOR |
|-------|-------|
| AI_PROVIDER | gemini (ou openai, claude, deepseek) |
| GEMINI_API_KEY | sua_chave_api_do_gemini |
| OPENAI_API_KEY | sua_chave_api_da_openai |
| CLAUDE_API_KEY | sua_chave_api_do_claude |
| DEEPSEEK_API_KEY | sua_chave_api_do_deepseek |
| PASTA_GOOGLE_DRIVE | ID_da_pasta_google_drive |

## Execução

Para iniciar a aplicação, execute:

```bash
cd formulario_culsen
python app.py
```

Acesse a aplicação em `http://localhost:5000`

## Funcionalidades

- Recebimento de formulários com dados do candidato e CV
- Upload automático dos CVs para o Google Drive
- Análise do CV utilizando diferentes modelos de IA
- Interface de administração para gerenciar candidatos e configurações
- Reprocessamento de CVs com diferentes provedores de IA
- Logs detalhados para diagnóstico de erros 
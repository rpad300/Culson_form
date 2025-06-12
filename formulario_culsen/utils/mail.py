import yagmail
from utils.sheets import get_config

def send_email(recipient_email, recipient_name, available_slots):
    """
    Send email to approved candidate with available interview slots
    """
    try:
        # Get email configuration from Google Sheets
        config = get_config()
        sender_email = config.get('EMAIL_REMETENTE')
        app_password = config.get('EMAIL_APP_PASSWORD')
        
        if not sender_email or not app_password:
            print("Email configuration not found.")
            return False
        
        # Initialize yagmail SMTP
        yag = yagmail.SMTP(sender_email, app_password)
        
        # Format available slots for email
        slots_html = ""
        for i, slot in enumerate(available_slots, 1):
            slots_html += f"""
            <div style="margin-bottom: 15px; padding: 10px; background-color: #f5f5f5; border-radius: 5px;">
                <strong>Opção {i}:</strong><br>
                Data: {slot['date']} ({slot['weekday']})<br>
                Horário: {slot['start_time']} - {slot['end_time']}
            </div>
            """
        
        # Create email content
        subject = "Candidatura Aprovada - Próximos Passos"
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #1a3a7c;">Parabéns, {recipient_name}!</h2>
            
            <p>Temos o prazer de informar que a sua candidatura foi <strong>aprovada</strong> para a próxima fase do processo seletivo.</p>
            
            <p>Gostaríamos de agendar uma entrevista consigo. Por favor, indique qual das seguintes opções de horário seria mais conveniente:</p>
            
            {slots_html}
            
            <p>Por favor, responda a este email indicando a sua preferência de horário.</p>
            
            <p>Caso nenhum dos horários seja conveniente, informe-nos e tentaremos encontrar uma alternativa.</p>
            
            <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee;">
                <p style="margin-bottom: 5px;"><strong>Equipe de Recrutamento</strong></p>
                <p style="margin-top: 0; color: #666;">Culsen</p>
            </div>
        </div>
        """
        
        # Send email
        yag.send(
            to=recipient_email,
            subject=subject,
            contents=html_content
        )
        
        return True
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False 
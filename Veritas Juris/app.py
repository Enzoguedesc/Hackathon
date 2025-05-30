# from flask import Flask, render_template, request, redirect, url_for, flash, session
# from flask_wtf import FlaskForm
# from wtforms import StringField, PasswordField, SubmitField
# from wtforms.validators import DataRequired
# from flask_wtf.recaptcha import RecaptchaField
# import os

# app = Flask(__name__, static_folder="static", template_folder="templates")
# app.secret_key = 'chave-secreta-segura'

# # Chaves do reCAPTCHA (use as suas)
# app.config['RECAPTCHA_PUBLIC_KEY'] = 'SUA_SITE_KEY'
# app.config['RECAPTCHA_PRIVATE_KEY'] = 'SUA_SECRET_KEY'

# USUARIO = {'username': 'admin', 'password': '1234'}
# chat_history = []

# class LoginForm(FlaskForm):
#     username = StringField('Usuário', validators=[DataRequired()])
#     password = PasswordField('Senha', validators=[DataRequired()])
#     recaptcha = RecaptchaField()
#     submit = SubmitField('Entrar')

# @app.route('/', methods=['GET', 'POST'])
# @app.route('/login', methods=['GET', 'POST'])
# def login():
#     form = LoginForm()
#     if form.validate_on_submit():
#         if form.username.data == USUARIO['username'] and form.password.data == USUARIO['password']:
#             session['user'] = form.username.data
#             return redirect(url_for('dashboard'))
#         else:
#             flash('Usuário ou senha incorretos.', 'error')
#     return render_template('login.html', form=form)

# @app.route('/dashboard', methods=['GET', 'POST'])
# def dashboard():
#     if 'user' not in session:
#         return redirect(url_for('login'))

#     global chat_history
#     if request.method == 'POST':
#         query = request.form['query']
#         chat_history.append({'role': 'Usuário', 'content': query})
#         resposta = buscar_jurisprudencia(query)
#         chat_history.append({'role': 'JurisBot', 'content': resposta})
    
#     return render_template('dashboard.html', chat_history=chat_history, user=session['user'])

# chat_history = []


# def simular_resposta_jurisprudencia(pergunta):
#     if "habeas corpus" in pergunta.lower():
#         return "Jurisprudência sobre habeas corpus: STJ, RHC 123456/SP, Rel. Min. Maria Silva, julgado em 20/05/2022..."
#     elif "dano moral" in pergunta.lower():
#         return "Em casos de dano moral, o STJ entende que..."
#     else:
#         return "Desculpe, não encontrei jurisprudência correspondente. Tente reformular a pergunta."


# @app.route('/logout')
# def logout():
#     session.pop('user', None)
#     flash('Você saiu com sucesso.', 'success')
#     return redirect(url_for('login'))

# def buscar_jurisprudencia(query):
#     # Simulação (pode integrar com banco ou GPT depois)
#     if "dano moral" in query.lower():
#         return "STJ - Ação de Dano Moral: REsp 100000/SP, rel. Min. João Silva, julgado em 01/01/2023."
#     elif "habeas corpus" in query.lower():
#         return "STF - Habeas Corpus 123456/SP, rel. Min. Maria Souza, julgado em 12/03/2022."
#     return "Desculpe, não encontrei jurisprudência correspondente."

# if __name__ == '__main__':
#     app.run(debug=True)

from flask import Flask, render_template, request, redirect, url_for, session, flash
import random
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, IntegerField
from wtforms.validators import DataRequired, NumberRange
from flask_wtf.csrf import CSRFProtect

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_aqui'  # Mude para algo seguro
csrf = CSRFProtect(app)

# Form com WTForms para CSRF e validação básica
class LoginForm(FlaskForm):
    email = StringField('Email ou Usuário', validators=[DataRequired()])
    password = PasswordField('Senha', validators=[DataRequired()])
    captcha = IntegerField('Captcha', validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField('Entrar')

def generate_captcha():
    n1 = random.randint(1, 10)
    n2 = random.randint(1, 10)
    return (n1, n2, n1 + n2)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    # Se não tem captcha na session, gera um novo
    if 'captcha_sum' not in session:
        n1, n2, s = generate_captcha()
        session['captcha_sum'] = s
        session['captcha_text'] = f"{n1} + {n2} = ?"

    if form.validate_on_submit():
        # Verifica captcha
        if form.captcha.data != session.get('captcha_sum'):
            flash('Resposta do CAPTCHA incorreta. Tente novamente.', 'error')
            # gera novo captcha
            n1, n2, s = generate_captcha()
            session['captcha_sum'] = s
            session['captcha_text'] = f"{n1} + {n2} = ?"
            return redirect(url_for('login'))

        email = form.email.data
        password = form.password.data

        # Aqui você coloca a lógica real de autenticação
        if email == "user@example.com" and password == "123456":
            session.pop('captcha_sum', None)
            session.pop('captcha_text', None)
            session['user'] = email
            flash('Login bem-sucedido!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Email ou senha incorretos.', 'error')
            # gera novo captcha
            n1, n2, s = generate_captcha()
            session['captcha_sum'] = s
            session['captcha_text'] = f"{n1} + {n2} = ?"
            return redirect(url_for('login'))

    return render_template('login.html', form=form, captcha_text=session.get('captcha_text'))

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    return f"Olá, {session['user']}! Bem-vindo ao dashboard."

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)

from flask import Flask, render_template, redirect, url_for, session, flash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired
from flask_wtf.recaptcha import RecaptchaField
import os

app = Flask(__name__)
app.secret_key = 'segredo-super-seguro'  # Use uma variável de ambiente no projeto real

# Configuração do ReCAPTCHA (use chaves válidas no deploy real)
app.config['RECAPTCHA_PUBLIC_KEY'] = '6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI'
app.config['RECAPTCHA_PRIVATE_KEY'] = '6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe'

USUARIO = {
    'email': 'admin@exemplo.com',
    'password': '1234'
}

class LoginForm(FlaskForm):
    email = StringField('Usuário', validators=[DataRequired()])
    password = PasswordField('Senha', validators=[DataRequired()])
    recaptcha = RecaptchaField()
    submit = SubmitField('Entrar')

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        if form.email.data == USUARIO['email'] and form.password.data == USUARIO['password']:
            session['user'] = form.email.data
            return redirect(url_for('dashboard'))
        else:
            flash('Usuário ou senha incorretos.', 'error')
    return render_template('login.html', form=form)

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    return f"Bem-vindo, {session['user']}!"

if __name__ == '__main__':
    app.run(debug=True)

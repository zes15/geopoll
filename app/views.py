from flask import render_template, json, request, flash, url_for, g, session
from flask_login import login_user, current_user, logout_user, login_required

from werkzeug.security import generate_password_hash
from werkzeug.utils import redirect
from flask_wtf import Form
from wtforms import validators, StringField, PasswordField, SelectField, IntegerField, RadioField
from wtforms.validators import InputRequired, Length, Email, NumberRange

from app import app, lm, db
from app.models.poll_whisperer import insert_new_poll, poll_search, get_polls_by_user, get_poll, insert_new_question, get_poll_questions, insert_new_response
from app.models.table_declaration import User
from app.models.user_whisperer import insert_new_user, account_sign_in, user_query, user_exists, \
    update_user_demographic_info, check_users, user_search


class signUpForm(Form):
    name = StringField('username', validators=[InputRequired(), Length(min=4,max=20)])
    email = StringField('email', validators=[InputRequired(), Email(message='Invalid email'), Length(max=50)])
    password = PasswordField('password', validators=[InputRequired(),Length(min=8, max=50)])


class signInForm(Form):
    name = StringField('username or email', validators=[InputRequired(), Length(min=4,max=50)])
    password = PasswordField('password', validators=[InputRequired(), Length(min=8, max=50)])


class searchForm(Form):
    search = StringField(validators=[InputRequired(),Length(min=4,max=50)])
    search_for = RadioField('search for', validators=[InputRequired()],
                                        choices=[('user', 'user'),
                                                 ('poll', 'poll')])

class pollForm(Form):
    poll_name = StringField(validators=[InputRequired(), Length(min=4, max=50)])

class pollQuestionAddForm(Form):
    question_text = StringField(validators=[InputRequired(), Length(min=4, max=50)])
    question_type = StringField(validators=[InputRequired(), Length(min=0, max=5)])
    question_choices = StringField(validators=[InputRequired(), Length(min=1, max=50)])


class demographicForm(Form):
    age = IntegerField('age',validators=[InputRequired(),NumberRange(min=0, max=120)])
    race = SelectField(u'race', choices=[('American Indian or Alaska Native','American Indian or Alaska Native'),
                                        ('Asian', 'Asian'),('Black or African American','Black or African American'),
                                        ('Hispanic or Latino','Hispanic or Latino'),
                                        ('Native Hawaiian or Other Pacific Islander','Native Hawaiian or Other Pacific Islander'),
                                        ('White','White'),('Other','Other')],
                       validators=[InputRequired()])
    gender = SelectField(u'gender', choices=[('Male','Male'),('Female','Female'),('Other','Other')],
                         validators=[InputRequired()])
    education = SelectField(u'education', choices=[('High School','High School'),
                                                  ('College (undergraduate)','College (undergraduate)'),
                                                  ('College (graduate)','College (graduate)'),
                                                  ('Technical School','Technical School'),
                                                   ('Other','Other')],
                            validators=[InputRequired()])


@app.route('/')
def main():
    return render_template('homepage.html')


@app.route('/showSignUp', methods=['GET','POST'])
def showSignUp():
    form = signUpForm(request.form)
    if form.validate_on_submit():
        _hashed_pword = generate_password_hash(form.password.data,'sha256')
        _name = form.name.data
        _email = form.email.data

        if user_exists(_name) is False:
            insert_new_user(_name, _email, _hashed_pword)
            print('user: ' + _name + ' has been entered into the db')
            return redirect(url_for('main'))
        else:
            print("That username is already taken.")
    return render_template('signup.html', form=form)


@app.route('/showSignIn', methods=['GET','POST'])
def showSignIn():
    form = signInForm()
    if form.validate_on_submit():
        _acc_name = form.name.data
        _pword = form.password.data

        if g.user is not None and g.user.is_authenticated:
            print('user is already logged in')
            return redirect(url_for('user', user_name=g.user.user_name))

        q = account_sign_in(_acc_name, _pword)
        if q is not None:
            session['remember_me'] = q.user_id
            login_user(q)
            print('SignIn successful')
            return redirect(url_for('user', user_name=q.user_name))
        else:
            print('Invalid Information. Please try again.')
    return render_template('signin.html', form=form)


@app.route('/user/<user_name>', methods=['POST','GET'])
@login_required
def user(user_name):
    user = user_query(user_name, 1)
    polls = get_polls_by_user(user.user_id)
    return render_template('user.html', user=user, polls=list(polls))


@app.route('/editInfo/<user_name>',methods=['POST','GET'])
@login_required
def edit(user_name):
    form = demographicForm()
    if form.validate_on_submit():
        _age= form.age.data
        _race = form.race.data
        _gender = form.gender.data
        _edu = form.education.data

        user = db.session.query(User).filter_by(user_name=g.user.user_name).first()
        if user.user_name is not None:
            print('user_name_in_edit', user.user_name)
            if update_user_demographic_info(user.user_name, _age, _race, _gender, _edu):
                print('Demographic Info was successfully updated')
                return redirect(url_for('user', user_name=user.user_name))
    return render_template('edit.html', user=g.user, form=form)


@app.route('/showSearch', methods=['POST','GET'])
@login_required
def search():
    form = searchForm()
    if form.validate_on_submit():
        search = form.search.data
        type = form.search_for.data
        return redirect(url_for('results', search=search, type=type))
    return render_template('search.html', form=form)


@app.route('/showResults/<type>/<search>', methods=['POST','GET'])
@login_required
def results(search, type):
    if type == 'user':
        results = user_search(search)
    elif type == 'poll':
        results = poll_search(search)
    return render_template('results.html',search=search, results=results, type=type, user=g.user)


@app.route('/showCreatePoll', methods=['POST','GET'])
@login_required
def showCreatePoll():
    form = pollForm()
    if form.validate_on_submit():
        _poll_name = form.poll_name.data
        insert_new_poll(_poll_name, g.user.user_name)
        return redirect(url_for('user', user_name=g.user.user_name))
    return render_template('createpoll.html',form=form)

@app.route('/poll/<poll_id>', methods=['post','get'])
def poll(poll_id):
    poll = get_poll(poll_id)
    questions = get_poll_questions(poll_id)
    question_dictionary = {}
    for question in questions:
        if question.question_type == "choice":
            choices = question.question_choices.split(",")
            question_dict_list = [question, choices]
            question_dictionary[question] = choices
        else:
            question_dictionary[question] = None
    print(question_dictionary)
    if request.method == 'POST':
        questions = []
        answers = []
        for answer in request.form:
            questions.append(answer)
            answers.append(request.form[answer])
        questions = ",".join(questions)
        answers = ",".join(answers)
        insert_new_response(poll_id, questions, answers)

    return render_template('poll.html', poll=poll, questions=question_dictionary, user=None)

@app.route('/poll/<poll_id>/add-question', methods=['post','get'])
def poll_add_question(poll_id):
    form = pollQuestionAddForm()
    print("Start Add Question Method")
    if request.form:
        print("Adding Question")
        print(request.form)
        print(request.form['question_text'])
        _question_text = request.form['question_text']
        _question_choices = request.form['question_choices']
        insert_new_question(_question_text, _question_choices, poll_id)
        return redirect(url_for('poll', poll_id=poll_id))
    poll = get_poll(poll_id)
    return render_template('poll_add_question.html', poll=poll, form=form)

@app.route('/poll/edit/<poll_id>', methods=['post','get'])
def poll_edit(poll_id):
    poll = get_poll(poll_id)
    return render_template('poll_edit.html', poll=poll)

@app.route('/poll/<poll_id>/summary', methods=['post','get'])
def poll_summary(poll_id):
    poll = get_poll(poll_id)
    return render_template('poll_summary.html', poll=poll)

@app.route('/signout')
def signOut():
    logout_user()
    print('SignOut was Success')
    return redirect(url_for('main'))


@lm.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.before_request
def before_request():
    g.user = current_user





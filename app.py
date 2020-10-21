
from flask import Flask,render_template,request,redirect,url_for,flash
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from datetime import datetime
from flask_wtf import FlaskForm
from flask_wtf.file import FileField,FileAllowed
from wtforms import StringField,PasswordField,SubmitField,BooleanField,RadioField,DateField,TextAreaField
from wtforms.validators import DataRequired,Length,EqualTo,ValidationError,Email
from flask_login import LoginManager,UserMixin,login_user,current_user,logout_user,login_required
import secrets
import os
from PIL import Image
import email_validator

app=Flask(__name__)
app.config['SECRET_KEY']='9816c160f4c8ba0d6c9f6f38fc08b37c'

app.config['SQLALCHEMY_DATABASE_URI']='sqlite:///posts.db'
db=SQLAlchemy(app)
bcrypt=Bcrypt(app)
login_manager=LoginManager(app)
login_manager.login_view='login'
login_manager.login_message_category='info'

class BlogPost(db.Model):
    id=db.Column(db.Integer,primary_key=True)
    content=db.Column(db.Text,nullable=False)
    date_posted=db.Column(db.DateTime,nullable=False,default=datetime.utcnow)
    image = db.Column(db.String(20), nullable=True)
    user_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False)



    def __repr__(self):
        return 'Blog post '+str(self.id)+":"+self.title


class User(db.Model,UserMixin):
    id=db.Column(db.Integer,primary_key=True)
    username=db.Column(db.String(20),nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    image_file=db.Column(db.String(20), nullable=False,default='default.jpg')
    password=db.Column(db.String(100), nullable=False)
    gender = db.Column(db.String(10), nullable=True, default='unknown')
    dob=db.Column(db.DateTime,nullable=True)
    posts=db.relationship('BlogPost',backref='author',lazy=True)
    friends=db.Column(db.Integer,nullable=False,default=0)
    last_studies=db.Column(db.String(100))
    job=db.Column(db.String(100))
    home=db.Column(db.String(100))


    def __repr__(self):
        return f"User('{self.username}','{self.password}','{self.image_file}')"

class Friendship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user1_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False)
    user2_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False)
    status=db.Column(db.Integer,nullable=False)

    def __repr__(self):
        return f"{self.user1_id}         {self.user2_id}"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class RegistrationForm(FlaskForm):
    username=StringField('Username',validators=[DataRequired(),Length(min=3,max=20)])
    email=StringField('Email',validators=[DataRequired(),Email()])
    password=PasswordField('Password',validators=[DataRequired(),Length(min=3,max=20)])
    confirm_password=PasswordField('Confirm Password',validators=[DataRequired(),EqualTo('password')])
    submit=SubmitField('Sign Up')

    def validate_email(self, email):
        mail = User.query.filter_by(email=email.data).first()
        if mail:
            raise ValidationError('An account already uses this email address.')

class LoginForm(FlaskForm):
    email=StringField('Email',validators=[DataRequired(),Length(min=3,max=20)])
    password=PasswordField('Password',validators=[DataRequired(),Length(min=3,max=20)])
    remember=BooleanField('Remember Me')
    submit=SubmitField('Login')

class UpdateForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=20)])
    picture=FileField('Profile Picture',validators=[FileAllowed(['jpg','jpeg','png'])])
    email = StringField('Email', validators=[DataRequired()])
    gender=RadioField('Gender',choices=[('Male','Male'),('Female','Female'),('Other','Other')])
    dob=DateField('Date of Birth',format="%Y-%m-%d")
    job=StringField('Actual Job')
    home=StringField('Where do you live')
    last_studies = StringField('Last Sudies')
    submit = SubmitField('Save')

    def validate_email(self, email):
        if email.data!=current_user.email:
            mail = User.query.filter_by(email=email.data).first()
            if mail:
                raise ValidationError('An account already uses this email address.')


class BlogPostForm(FlaskForm):
    content=TextAreaField('What you think?',validators=[Length(min=0,max=1000),DataRequired()])
    image=FileField('Add an Image.',validators=[FileAllowed(['jpg','jpeg','png'])])



class SearchForm(FlaskForm):
    username=StringField('Who are you looking for',validators=[Length(min=1,max=20),DataRequired()])


@app.route('/',methods=['GET'])
def home():
    return redirect('/posts')

@app.route("/register", methods=['GET', 'POST'])
def register():
    if(current_user.is_authenticated):
        return redirect(url_for('posts'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password=bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user=User(username=form.username.data,email=form.email.data,password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash(f'Your account has been created', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

@app.route('/login',methods=['GET','POST'])
def login():
    if (current_user.is_authenticated):
        return redirect(url_for('posts'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page=request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('posts'))
        else:
            flash('Login Unsuccessful. Please check username and password.', 'danger')
    return render_template('login.html', title='Login', form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/posts',methods=['GET','POST'])
@login_required
def posts():
    form2 = SearchForm()
    form = BlogPostForm()
    requests = len(Friendship.query.filter_by(user2_id=current_user.id, status=0).all())
    if form.validate_on_submit():
        if form.image.data:
            picture=save_post_picture(form.image.data)
            new_post = BlogPost(content=form.content.data, user_id=current_user.id, image=picture)
        else:
            new_post = BlogPost(content=form.content.data, user_id=current_user.id)
        db.session.add(new_post)
        db.session.commit()
        return redirect('/posts')
    elif form2.validate_on_submit():
        return redirect('/search/'+form2.username.data)
    elif request.method=='GET':
        all_posts = BlogPost.query.order_by(BlogPost.date_posted.desc()).all()
        return render_template('posts.html',posts=all_posts,no_posts=len(all_posts),form=form,form2=form2,requests=requests)


@app.route('/posts/delete/<int:id>')
def delete(id):
    post=BlogPost.query.get_or_404(id)
    db.session.delete(post)
    db.session.commit()
    return redirect('/posts')


def save_post_picture(form_picture):
    random_hex=secrets.token_hex(8)
    _,f_ext=os.path.splitext(form_picture.filename)
    picture=random_hex+f_ext
    picture_path=os.path.join(app.root_path,"static/post_pics",picture)
    output_size=(500,500)
    i=Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)
    return picture



@app.route("/profile/<int:id>",methods=['GET','POST'])
@login_required
def profile(id):
    form2 = SearchForm()
    user=User.query.get_or_404(id)
    image_file=url_for('static',filename='profile_pics/' + user.image_file)
    add_icon=url_for('static',filename='icons/add1.png')
    remove_icon=url_for('static',filename='icons/remove1.png')
    all_posts = BlogPost.query.order_by(BlogPost.date_posted.desc()).all()
    all_users = User.query.all()
    friendship1=Friendship.query.filter_by(user1_id=current_user.id,user2_id=user.id).first()
    friendship2 = Friendship.query.filter_by(user1_id=user.id, user2_id=current_user.id).first()
    friendships=Friendship.query.all()
    requests=len(Friendship.query.filter_by(user2_id=current_user.id,status=0).all())
    if form2.validate_on_submit():
        return redirect('/search/'+form2.username.data)
    return render_template('profile.html',title="Profile",image_file=image_file,posts=all_posts,user=user
                           ,all_users=all_users,friendship1=friendship1,friendship2=friendship2
                           ,requests=requests,friendships=friendships,add_icon=add_icon,remove_icon=remove_icon
                           ,form2=form2)

def save_picture(form_picture):
    random_hex=secrets.token_hex(8)
    _,f_ext=os.path.splitext(form_picture.filename)
    picture=random_hex+f_ext
    picture_path=os.path.join(app.root_path,'static/profile_pics',picture)
    output_size=(125,125)
    i=Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)

    return picture


@app.route("/settings",methods=['GET','POST'])
@login_required
def settings():
    form=UpdateForm()
    form2 = SearchForm()
    requests = len(Friendship.query.filter_by(user2_id=current_user.id, status=0).all())
    if form.validate_on_submit():
        if form.picture.data:
            picture_file=save_picture(form.picture.data)
            current_user.image_file=picture_file
        current_user.username = form.username.data
        current_user.email = form.email.data
        current_user.gender = form.gender.data
        current_user.dob = form.dob.data
        current_user.home=form.home.data
        current_user.job=form.job.data
        current_user.last_studies=form.last_studies.data
        db.session.commit()
        flash(f'Your account has been updated successfuly!', 'success')
        return redirect(url_for('settings'))
    elif form2.validate_on_submit():
        return redirect('/search/'+form2.username.data)
    elif request.method=='GET':
        form.username.data=current_user.username
        form.email.data=current_user.email
        form.gender.data=current_user.gender
        form.dob.data=current_user.dob
        form.home.data=current_user.home
        form.job.data=current_user.job
        form.last_studies.data=current_user.last_studies
    return render_template("settings.html",title='Settings',form=form,requests=requests,form2=form2)


@app.route("/add_friendship/<int:id1>/<int:id2>")
@login_required
def add_friendship(id1,id2):
    friendship1 = Friendship.query.filter_by(user1_id=id1, user2_id=id2).first()
    friendship2 = Friendship.query.filter_by(user1_id=id2, user2_id=id1).first()
    if not friendship1 and not friendship2:
        new_friendship=Friendship(user1_id=id1,user2_id=id2,status=0)
        db.session.add(new_friendship)
        db.session.commit()
    return redirect('/profile/'+str(id2))

@app.route("/delete_friendship/<int:id1>/<int:id2>")
@login_required
def delete_friendship(id1,id2):
    friendship1=Friendship.query.filter_by(user1_id=id1,user2_id=id2).first()
    friendship2 = Friendship.query.filter_by(user1_id=id2, user2_id=id1).first()
    user1 = User.query.filter_by(id=id1).first()
    user1.friends=user1.friends-1
    user2 = User.query.filter_by(id=id2).first()
    user2.friends=user2.friends-1
    db.session.delete(friendship1)
    db.session.delete(friendship2)
    db.session.commit()
    return redirect('/profile/'+str(id2))

@app.route("/accept_friendship/<int:friendship_id>")
@login_required
def accept_friendship(friendship_id):
    friendship=Friendship.query.filter_by(id=friendship_id).first()
    if friendship.status==0:
        friendship.status=1
        new_friendship=Friendship(user1_id=friendship.user2_id,user2_id=friendship.user1_id,status=1)
        db.session.add(new_friendship)
        user1=User.query.filter_by(id=friendship.user1_id).first()
        user1.friends=user1.friends+1
        user2 = User.query.filter_by(id=friendship.user2_id).first()
        user2.friends = user2.friends + 1
        db.session.commit()
    return redirect('/profile/' + str(friendship.user2_id))

@app.route("/ignore_friendship/<int:friendship_id>")
@login_required
def ignore_friendship(friendship_id):
    friendship=Friendship.query.get_or_404(friendship_id)
    db.session.delete(friendship)
    db.session.commit()
    return redirect('/profile/' + str(friendship.user2_id))


@app.route("/search/<string:username>")
@login_required
def search(username):
    add_icon = url_for('static', filename='icons/add1.png')
    remove_icon = url_for('static', filename='icons/remove1.png')
    requests = len(Friendship.query.filter_by(user2_id=current_user.id, status=0).all())
    usr=username.upper()
    users=User.query.all()
    matched_users=[]
    friendships = Friendship.query.all()
    form2 = SearchForm()
    if form2.validate_on_submit():
        return redirect('/search/'+form2.username.data)
    for user in users:
        name=user.username.upper()
        if name[0]==usr[0] and name[1]==usr[1] and name[2]==usr[2]:
            matched_users.append(user)
    return render_template("search_result.html",title="Search Result",matched_users = matched_users,ln=len(matched_users)
                           ,add_icon=add_icon,remove_icon=remove_icon,friendships=friendships,requests=requests
                           ,form2=form2)

@app.route("/friend_requests")
@login_required
def friend_requests():
    form2 = SearchForm()
    form3 = SearchForm()
    add_icon = url_for('static', filename='icons/add1.png')
    remove_icon = url_for('static', filename='icons/remove1.png')
    friendships = Friendship.query.filter_by(user2_id=current_user.id, status=0).all()
    requests = len(Friendship.query.filter_by(user2_id=current_user.id, status=0).all())
    all_users = User.query.all()
    return render_template('friend_requests.html',title='Friend Requests',add_icon=add_icon,remove_icon=remove_icon,friendships=friendships
                           ,requests=requests,all_users=all_users,form2=form2,form3=form3)

if __name__=="__main__":
    app.run(debug=True)

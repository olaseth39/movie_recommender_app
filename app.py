from flask import Flask,render_template, flash, request,redirect, url_for, session,logging, send_from_directory
from flask_mysqldb import MySQL
from wtforms import Form, StringField, TextAreaField, PasswordField, validators,IntegerField
from passlib.hash import sha256_crypt #for password encryption
from functools import wraps #for decorator
from flask_ckeditor import CKEditorField,CKEditor
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from werkzeug.utils import secure_filename
from sklearn.neighbors import NearestNeighbors #for model design
from sklearn.neighbors import KNeighborsClassifier #for model design
import os
import numpy as np
#from settings import PROJECT_ROOT

# from data import Posts

#instantiate Flask method
app = Flask(__name__)

#logging.basicConfig(level=logging.DEBUG)
# config MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'movie_app'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

#initialize MySQL
mysql = MySQL(app)

#initialize ckeditor
ckeditor = CKEditor(app)

# Posts = Posts()
#create the home route
@app.route("/")
def home():
    #create cursor
    cur = mysql.connection.cursor()

    #Get articles 
    result = cur.execute("SELECT * FROM movies LIMIT 30")

    movies = cur.fetchall() #fecth in dictionary format

    if result > 0:
        return render_template('home.html', movies=movies)
    else:
        msg = 'No Articles found'
        return render_template('home.html', msg=msg)

    #commit connection
    cur.commit()

    #close connection
    cur.close()

    #return render_template("home.html")

#about us
@app.route("/aboutus.html")
def aboutus():
    return render_template("aboutus.html")

#posts
@app.route("/posts.html")
def posts():
    #create cursor
    cur = mysql.connection.cursor()

    #Get articles 
    result = cur.execute("SELECT * FROM articles")

    articles = cur.fetchall() #fecth in dictionary format

    if result > 0:
        return render_template('posts.html', articles=articles)
    else:
        msg = 'No Articles found'
        return render_template('posts.html', msg=msg)

    #close connection
    cur.close()

#post
@app.route("/post/<string:id>/")
def post(id):
    #create cursor
    cur = mysql.connection.cursor()

    #Get articles 
    result = cur.execute("SELECT * FROM articles WHERE id= %s", [id])
    if result == 1: #this is just to make use of result,it's not needed
        article = cur.fetchone() #fecth in dictionary format
    return render_template("post.html", article=article)

#register form
class RegisterForm(Form):
     name = StringField('Name', [validators.length(min=1, max=50), validators.DataRequired()])
     email = StringField('Email', [validators.length(min=6, max=50), validators.DataRequired()])
     password = PasswordField('Password', [
         validators.DataRequired(),
         validators.EqualTo('confirm', message='Passwords do not match')
     ])
     confirm = PasswordField('Confirm Password')

#register
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm(request.form)
    # check if it's a POST reqiest and validate
    if request.method == 'POST' and form.validate():
        #get the data in the form
        name = form.name.data
        email = form.email.data
        password = sha256_crypt.encrypt(str(form.password.data))

        #Create cursor
        cur = mysql.connection.cursor()

        cur.execute('INSERT INTO users(name, email, password) VALUES(%s, %s, %s)', (name, email, password))

        #commit to db
        mysql.connection.commit()

        #close connection
        cur.close()

        #set a flash message
        flash('Registeration is successful. You can now log in.', 'success')

        return redirect(url_for('login'))
    return render_template('register.html', form=form)

#user login
@app.route('/login', methods = ['GET', 'POST'])
def login():
    if request.method == 'POST':
        #Get from fields, note we are not using wtform here instead we are using the request method to get the data from the form.
        email = request.form['email']
        password_candidate = request.form['password']

        #create a cursor
        cur = mysql.connection.cursor()

        #get user by email
        result = cur.execute("SELECT * FROM users WHERE email = %s", [email]) 

        #check the result if any is found
        if result > 0:
            #get stored hashed password
            data = cur.fetchone()
            password = data['password']

            #compare passwords
            if sha256_crypt.verify(password_candidate, password):
               session['logged_in'] = True
               session['email'] = email
               num = data['user_id']      #get the user_id
               session['num'] = num        #keep user_id in session

               flash('You are now logged in', 'success')
               return redirect(url_for('dashboard', id=data['user_id']))
               
            else:
                error = 'Invalid login'
                return render_template('login.html', error=error)
            #close connection
            cur.close()
        else:
            error = 'Email not found'
            return render_template('login.html', error=error)

    return render_template('login.html')

#check if user logged
def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash('Unauthorized, Please Login', 'danger')
            return redirect(url_for('login'))
    return wrap
    
#logout
@app.route('/logout')
@is_logged_in
def logout():
    session.clear()
    flash('You are logged out', 'success')
    return redirect(url_for('home'))

#dashboaed with id
@app.route('/dashboard/<string:id>/')
@is_logged_in
def dashboard(id):
    #fetch all aeticles from database
    #create cursor
    cur = mysql.connection.cursor()

    #Get articles 
    result = cur.execute("SELECT articles.*, users.* \
                          FROM articles \
                          INNER JOIN users ON articles.author = users.email \
                          WHERE users.user_id = %s",[id])

    articles = cur.fetchall() #fecth in dictionary format

    if result > 0:
        return render_template('dashboard.html', articles=articles)
    else:
        msg = 'No Articles found'
        return render_template('dashboard.html', msg=msg)

    #close connection
    cur.close()

#Article form class
class ArticleForm(Form):
     title = StringField('Title', [validators.length(min=1, max=200), validators.DataRequired()])
     body = CKEditorField('Body', [validators.length(min=30), validators.DataRequired()]) 

#Add Articles
@app.route('/add_article/<string:id>', methods=['GET','POST'])
@is_logged_in
def add_article(id):
    #instantiate the ArticleForm
    form = ArticleForm(request.form)
    #check the request method and validation
    if request.method == 'POST' and form.validate():
        title = form.title.data #get the title field
        body = form.body.data  #get the body field

        #Create Cursor
        cur = mysql.connection.cursor()

        #Execute
        cur.execute('INSERT INTO articles(title, body, author) VALUES(%s, %s, %s)', (title, body, session['email']))

        #Connect to DB
        mysql.connection.commit()

        #close connection
        cur.close()

        flash('Article Created', 'success')

        return redirect(url_for('dashboard',id=id)) 
        #return render_template('dashboard.html')

    return render_template('add_article.html', form=form)   

#Edit Articles
@app.route('/edit_article/<string:id>', methods=['GET','POST'])
@is_logged_in
def edit_article(id):
    #we need to get the the row we want to query
    cur = mysql.connection.cursor()

    #get the article by id 
    result = cur.execute("SELECT * FROM articles WHERE id = %s", [id])
    if result == 1:
        article = cur.fetchone()

    #instantiate the ArticleForm
    form = ArticleForm(request.form)

    #populate article from fields
    form.title.data = article['title']
    form.body.data  = article['body']

    #check the request method and validation
    if request.method == 'POST' and form.validate():
        title = request.form['title'] #get the title field
        body = request.form['body']  #get the body field

        #Create Cursor
        cur = mysql.connection.cursor()

        #Execute
        cur.execute('UPDATE articles SET title=%s, body=%s WHERE id=%s', (title, body, [id]))

        #Connect to DB
        mysql.connection.commit()

        #close connection
        cur.close()

        flash('Article Edited', 'success')

        return redirect(url_for('dashboard', id=session['num'])) 

    return render_template('edit_article.html', form=form)

#delete route
@app.route('/delete_article/<string:id>', methods=['POST'])
@is_logged_in
def delete_article(id):
    #create cursor
    cur = mysql.connection.cursor()

    #execute
    cur.execute("DELETE FROM articles WHERE id = %s", [id])

    #connect to db
    mysql.connection.commit()

    #close connection
    cur.close()

    #send a flash success message
    flash('Article Deleted', 'success')

    return redirect(url_for('dashboard', id=session['num']))

#form class for posting movies to database
class MoviesForm(FlaskForm):
    title = StringField('Title', [validators.length(min=3), validators.DataRequired()])
    rating = IntegerField(' Give Rating',[validators.DataRequired()])
    movie_image = FileField('Upload Movie Picture', validators=[FileRequired()])

#app.instance_path
app.config['ALLOWED_IMAGE_EXTENSIONS'] = ['PNG', 'JPG', 'JPEG', 'GIF']
app.config['IMAGE_UPLOADS'] = 'static/uploads/movie_image/'
#app.config['MAX_IMAGE_LENGTH'] = 16 * 1024 * 1024

def allowed_image(filename):

    if not '.' in filename:
        flash('Invalid file', category='error')
        return redirect(request.url)

    #split filename from the right
    ext = filename.rsplit('.', 1)[1]

    if ext.upper() in app.config['ALLOWED_IMAGE_EXTENSIONS']:
        return True
    else:
        return False

@app.route('/add_movie', methods=['GET', 'POST'])
def upload_file():

    form = MoviesForm()

    if request.method == 'POST':

        title = form.title.data #get the title field
        
        rating = form.rating.data #get the rating field
        
        movie_image = form.movie_image.data #get the image field
        
        #check for an empty field
        if movie_image.filename == '':
            flash('No image selected',category='error')
            return redirect(request.url)

        #check for the correct extension
        if not allowed_image(movie_image.filename):
            flash('Invalid image extension', category='error')
            return redirect(request.url)

        else:
            #sanitize the filename
            filename = secure_filename(movie_image.filename)
        
        #save the image
        movie_image.save(os.path.join(app.config['IMAGE_UPLOADS'], filename)) 
        #.filename is an attribute of the movie_image object

        #create cursor
        cur = mysql.connection.cursor()

        #send to db
        cur.execute("INSERT INTO movies(title, rating, image) VALUES(%s, %s, %s)", (title, rating, filename))

        #commit
        cur.connection.commit()

        #close connection
        cur.close()
        
        flash('Infomation saved successfully!', category='success')
        return redirect(url_for('dashboard'))

    return render_template('add_movie.html', form=form)

#each movie
@app.route('/movie/<string:id>/')
def movie(id):
    #create cursor
    cur = mysql.connection.cursor()

    #get all movies,rating and vote count
    all_data = cur.execute("SELECT id, rating, popularity FROM movies")

    #fetch in dictionary format
    data = cur.fetchall()

    #connect to db
    cur.connection.commit()
    #close connection
    #cur.close()

    #Get a movie 
    result = cur.execute("SELECT id, title, rating, image, popularity, overview, date FROM movies WHERE id= %s", [id])
    if result == 1: #this is just to make use or result,it's not needed
        movie = cur.fetchone() #fecth in dictionary format

    #model to get recommendation
    #1 instantiate the NearestNeighbor class
    knn = NearestNeighbors(metric='cosine', algorithm='brute', n_neighbors=15)
    value = [m for m in movie.values() if (type(m) == int) | (type(m) == float)] #select values for x
    data_list = [] #create an empty list
    for i in data: #get each value in the tuple data
        data_list.append(list(i.values())) #append only the values in the dictionary and convert to list
    #print(a)
    knn.fit(data_list) #train the model
    distances,indices = knn.kneighbors([value], n_neighbors=4) 
    print(indices)

    #query the database to get all data in movies table
    #this is to get all the data as we dont have them in the other queries in this function for all data
    #create cursor
    cur = mysql.connection.cursor()

    #get all movies,rating and vote count
    movies = cur.execute("SELECT * FROM movies")

    #fetch in dictionary format
    movies = cur.fetchall()

    #connect to db
    cur.connection.commit()

    #iterate throughthe indices to get each values
    for i in indices:
        rec_movies = np.array(movies)[i]
        #print(rec_movies)

    return render_template("movie.html", movie=movie, rec_movies=rec_movies)


if __name__ == "__main__":
    app.secret_key='secret123'
    app.run(debug=True)
    



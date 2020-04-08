#Import Flask Library
from flask import Flask, render_template, request, session, url_for, redirect,flash
from werkzeug.utils import secure_filename
import hashlib
import os
import pymysql.cursors
SALT = 'cs3083'
ALLOWED_EXTENSIONS = set(['png','jpg','jpeg','gif','bmp'])
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

#Initialize the app from Flask
app = Flask(__name__)

#Configure MySQL
conn = pymysql.connect(host='localhost',
                       port = 8889,
                       user='root',
                       password='root',
                       db='dbproject',
                       charset='utf8mb4',
                       cursorclass=pymysql.cursors.DictCursor)

#Define a route to hello function
@app.route('/')
def hello():
    return render_template('index.html')
    # return 'hello world'

#Define route for login
@app.route('/login')
def login():
    return render_template('login.html')

#Define route for register
@app.route('/register')
def register():
    return render_template('register.html')

#Authenticates the login
@app.route('/loginAuth', methods=['GET', 'POST'])
def loginAuth():
    #grabs information from the forms
    username = request.form['username']
    password = request.form['password']+SALT
    hashed_password = hashlib.sha256(password.encode('utf-8')).hexdigest()

    #cursor used to send queries
    cursor = conn.cursor()
    #executes query
    query = 'SELECT * FROM Person WHERE username = %s and password = %s'
    cursor.execute(query, (username, hashed_password))
    #stores the results in a variable
    data = cursor.fetchone()
    #use fetchall() if you are expecting more than 1 data row
    cursor.close()
    error = None
    if(data):
        #creates a session for the the user
        #session is a built in
        session['username'] = username
        return redirect(url_for('home'))
    else:
        #returns an error message to the html page
        error = 'Invalid login or username'
        return render_template('login.html', error=error)

#Authenticates the register
@app.route('/registerAuth', methods=['GET', 'POST'])
def registerAuth():
    #grabs information from the forms
    username = request.form['username']
    password = request.form['password']+SALT
    hashed_password = hashlib.sha256(password.encode('utf-8')).hexdigest()
    fname = request.form['fname']
    lname = request.form['lname']
    email = request.form['email']

    #cursor used to send queries
    cursor = conn.cursor()
    #executes query
    query = 'SELECT * FROM Person WHERE username = %s'
    cursor.execute(query, (username))
    #stores the results in a variable
    data = cursor.fetchone()
    #use fetchall() if you are expecting more than 1 data row
    error = None
    if(data):
        #If the previous query returns data, then user exists
        error = "This user already exists"
        return render_template('register.html', error = error)
    else:
        ins = 'INSERT INTO Person VALUES(%s, %s, %s, %s, %s)'
        cursor.execute(ins, (username, hashed_password, fname,lname,email))
        conn.commit()
        cursor.close()
        return render_template('index.html')


@app.route('/home')
def home():
    user = session['username']
    cursor = conn.cursor();

    # query = 'SELECT  postingDate, pID, firstName,lastName,filePath FROM Photo AS ph JOIN Person AS p ON(p.username = ph.poster)WHERE(ph.poster = %s)OR (allFollowers = 1 AND %s IN (SELECT follower FROM Follow WHERE followee = ph.poster AND followStatus = 1)) OR (allFollowers = 0 AND %s IN (SELECT username FROM BelongTo WHERE (groupName, groupCreator) IN (SELECT groupName, groupCreator FROM SharedWith WHERE pID = ph.pID))) ORDER BY postingDate DESC'
    query = 'SELECT postingDate, pID, firstName,lastName,filePath FROM Photo JOIN Follow ON(poster = followee) JOIN Person ON(poster = username) WHERE follower = %s AND allFollowers = 1 AND followStatus = 1 UNION (SELECT postingDate, pID, firstName,lastName,filePath FROM Photo JOIN Person ON(poster = Person.username) WHERE pID IN (SELECT pID FROM SharedWith NATURAL JOIN BelongTo WHERE username = %s))ORDER BY postingDate DESC'
    cursor.execute(query, (user, user))

    data = cursor.fetchall()
    # print(data)
    cursor.close()
    return render_template('home.html', username=user, posts=data)

@app.route('/createGroup')
def create_group():
    username = session['username']
    return render_template('create_group.html')

@app.route('/createAuth', methods=['GET', 'POST'])
def createAuth():
    username = session['username']
    groupName = request.form['groupName']
    description = request.form['description']
    #start curosr
    cursor = conn.cursor()
    query = 'SELECT * FROM FriendGroup WHERE groupName = %s AND groupCreator = %s'
    cursor.execute(query, (groupName,username))
    data = cursor.fetchone()
    error = None
    if(data):
        #If the previous query returns data, then user exists
        error = "This group already exists"
        return render_template('create_group.html', error = error)
    else:
        #create new group
        create_query = 'INSERT INTO FriendGroup VALUES(%s, %s,%s)'
        #add the creator as a member to the new group
        belong_query = 'INSERT INTO BelongTo VALUES(%s, %s,%s)'
        cursor.execute(create_query,(groupName, username, description))
        cursor.execute(belong_query,(username,groupName,username))
        conn.commit()
        cursor.close()
        return redirect(url_for('home'))






        
@app.route('/post', methods=['GET', 'POST'])
def post():
    username = session['username']
    if request.method == 'POST':
        file = request.files['file']
        caption = request.form['caption']
        shared_groups = request.form.getlist('shared_groups')
        all_followers = int(request.form['all_followers'])

        if file and allowed_file(file.filename):
            # save photo to a dedicated folder
            basepath = os.path.dirname(__file__)
            upload_path = os.path.join(basepath,'static/images', secure_filename(file.filename))
            file.save(upload_path)


            cursor = conn.cursor();
            photo_query = 'INSERT INTO Photo (postingDate,allFollowers,caption,poster) VALUES(NOW(),%s,%s,%s)'
            shared_with_query = 'INSERT INTO SharedWith (pID,groupName,groupCreator)VALUES(LAST_INSERT_ID(),%s,%s)'
            update_path = 'UPDATE Photo SET filePath = %s WHERE pID = %s'
            #insert info to Photo
            cursor.execute(photo_query, (all_followers, caption, username))

            #rename file as pID and upload filrpath
            get_ID = 'SELECT LAST_INSERT_ID() AS pID FROM Photo'
            cursor.execute(get_ID)

            pID = cursor.fetchone()['pID']
            filePath = '/static/images/'+str(pID)+'.jpg'
            cursor.execute(update_path,(filePath,pID))

            os.rename(upload_path,os.path.join(basepath,'static/images',str(pID)+'.jpg'))


            #update sharedWith
            for i in shared_groups:
                group = i.split(',')
                groupName = group[0]
                groupCreator = group[1]
                cursor.execute(shared_with_query,(groupName,groupCreator))
            conn.commit()
            cursor.close()
            return redirect(url_for('home'))
        else:
            flash('No file or filr type not supported')
            return redirect(url_for('post_photo'))


@app.route('/post_photo')
def post_photo():
    username = session['username']
    cursor = conn.cursor();
    query = 'SELECT DISTINCT groupName, groupCreator FROM BelongTo WHERE username = %s'
    cursor.execute(query,(username))
    groups = cursor.fetchall()
    cursor.close()
    return render_template('post_photo.html',groups = groups)
    

@app.route('/select_blogger')
def select_blogger():
    #check that user is logged in
    #username = session['username']
    #should throw exception if username not found
    
    cursor = conn.cursor();
    query = 'SELECT DISTINCT username FROM blog'
    cursor.execute(query)
    data = cursor.fetchall()
    cursor.close()
    return render_template('select_blogger.html', user_list=data)

@app.route('/show_posts', methods=["GET", "POST"])
def show_photo(filePath):
    
    return render_template('show_photp.html', filePath = filePath)

@app.route('/logout')
def logout():
    session.pop('username')
    return redirect('/')
        
app.secret_key = 'some key that you will never guess'
#Run the app on localhost port 5000
#debug = True -> you don't have to restart flask
#for changes to go through, TURN OFF FOR PRODUCTION
if __name__ == "__main__":
    app.run('127.0.0.1', 5000, debug = True)

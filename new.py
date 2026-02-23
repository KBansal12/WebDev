print("Hello, World!")
#WSGI Server is use to convert the web server request to a python callable object(web url to python understanding)
#WSGI stands for Web Server Gateway Interface
#It acts as a bridge between web servers and web applications or frameworks written in Python.  
#Popular WSGI servers include Gunicorn, uWSGI, and Waitress.
app = Flask(__name__)
app.config.from_object(Config)
app.config_key =app.config('SECRET_KEY')

def connect_to_database():
    connection = pymysql.connect(
        host=app.config['MYSQL_HOST'],
        user=app.config['MYSQL_USER'],
        password=app.config['MYSQL_PASSWORD'],
        db=app.config['MYSQL_DB'],
        port=app.config['MYSQL_PORT']
    )
    return connection
#Web server(url)->WsGI server(url to python)->flask Application(python code)->database(mysql,sqlite,mongodb)->flask Application(python code)->WSGI server(python to url)->web server(url)
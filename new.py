print("Hello, World!")
#WSGI Server is use to convert the web server request to a python callable object(web url to python understanding)
#WSGI stands for Web Server Gateway Interface
#It acts as a bridge between web servers and web applications or frameworks written in Python.  
#Popular WSGI servers include Gunicorn, uWSGI, and Waitress.
#Web server(url)->WsGI server(url to python)->flask Application(python code)->database(mysql,sqlite,mongodb)->flask Application(python code)->WSGI server(python to url)->web server(url)
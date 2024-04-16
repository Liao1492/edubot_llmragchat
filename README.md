
## Getting Setup

### Getting Started Locally

#### Just Run the Application

1. **Change the value in the .env file, important to add your own OpenAI Secret Key**

2. Build Docker Images

```commandline
sudo docker-compose -f local.yml build
or
sudo docker-compose -f local.yml up -d --build   (dev mode)
```

3. Launch the application you can type ( second commnad ):

```commandline
sudo docker-compose --profile fullstack -f local.yml up
```
4 Lunch front end application
```commandline

cd frontend
npm i 
npm run dev

```
# Using the Application

### First, Setup a Django superuser:

1. Run the following command to create a superuser:

```
sudo docker-compose -f local.yml run django python manage.py createsuperuser
```

2. You will be prompted to provide a username, email address, and password for the superuser. Enter the required information.


# Setting up google auth

- Set up an account on [Google Cloud](https://console.cloud.google.com/) - it's free

- Navigate to an existing project or create a new one.

- Navigate to [APIs & Services](https://console.cloud.google.com/apis/dashboard)

- Go to enabled APIs & services
    - Enable Google Docs API
    - Enable Google Drive API

- Back in APIs & Services, go to "OAuth consent screen"
    - Configure your consent screen
    - Since we're still in testing mode, all users of your app need to be added manually in the Oauth consent screen section. Other users won't have access to the app yet
    - Make sure to add the scopes required for your app
    - In this case we want ".../auth/userinfo.email" and ".../auth/documents.readonly"

- Back in APIs & Services, navigate to "Credentials"
    - Create a new Oauth client ID
    - Note the client ID and client secret - they are needed in your .env file
    - Under "authorized redirect URIs", add "http://localhost:5000/api/login"


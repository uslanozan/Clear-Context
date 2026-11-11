# Read-only demo

The demo at <https://clearcontext.uslanozan.com.tr/demo/> is the web app built in demo mode. It
has no server: every read comes from recorded JSON files beside it, and every change, new
investigation or paid action is refused. Settings are not part of it.

To rebuild it:

1. Start a server on a database that holds the reports to show (only GET requests are made, so
   nothing runs or is billed), then export them:

   ```powershell
   .\.venv\Scripts\python.exe packaging/demo/export_demo.py frontend/public-demo-data --server http://127.0.0.1:8000 <investigation-id> ...
   ```

   Running it again against another server adds to the same history. The export keeps only
   about 200 characters around each quoted passage of a source page, so the demo does not
   republish whole third-party pages, and removes email addresses outside the quotes.
   Settings and API keys are never exported.

2. Build the app for `/demo/` and copy it with the data into the website's `demo/` folder:

   ```powershell
   cd frontend
   npm run build:demo
   # dist-demo/ -> <website>/demo/, public-demo-data/ -> <website>/demo/data/
   ```

The demo uses `#` routes, so the web server needs no extra rule for links into a report.

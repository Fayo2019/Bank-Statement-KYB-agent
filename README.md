## Bank Statement Verification & Fraud Detection Tool

This python code automates the verification of business bank statements, extracting information and identifying potential fraud signals as part of KYB (Know Your Business) and AML (Anti-Money Laundering) processes for onboarding new business.


## Features

- **Document Classification**: Determines if a document is a business bank statement
   1. Converts PDF to images for multi modal model analysis
   2. Uses pattern recognition to classify document type

- **Business Details Extraction and Checking**: Extracts business name, address, and account information before verifying that transaction amounts reconcile with reported balances.

- **Fraud Detection**: After clarifying the document is a financial statement, we ensure it isn't fraudulent. The current checks are:

   1. Visual analysis: Examines document for visual anomalies (e.g. missing logo)
   2. Structural analysis: Examines PDF objects for suspicious elements/objects
   3. Financial analysis: Flags unexplained discrepancies/potential placeholders
   4. Transaction analysis: checks for errors or anomolies in transactions on statement

- **Risk Assessment**
   - Calculates an overall fraud risk score
   - Categorizes risk level (Minimal, Low, Medium, High)
   - Provides specific risk breakdown with components (mentioned above)
   - Code returns a summary report in the console and a JSON analysis file (in the directory of the pdf)


## Setup

1. Ensure you're using python 3.12 in your interpreter (this code can also be ran in a venv instead of the base machine to set the python version easily).

2. Install Python dependencies: use terminal command 'pip install -r requirements.txt'.

3. Install Poppler (required for pdf2image):
   - macOS: `brew install poppler`
   - Ubuntu/Debian: `apt-get install poppler-utils`
   - Windows: [Download binaries](https://github.com/oschwartz10612/poppler-windows/releases/)

4. Create a .env file in the root directory of the format: 
```env
OPENAI_API_KEY=<your-openai-key>
OPENAI_MODEL=<openai-omni-model(I use gpt4o)>
```


## Usage

Run the tool on any PDF document from the terminal: 
1. cd to the root directory
2. Use the command 'python src/main.py path/to/bank_statement.pdf'
   - -v adds verbose
   - -o path-to-reports-directory saves the report to a specific directory (defaults to the directory of the document being analysed)


## Extending the Tool

This MVP can be extended in several ways:
- Identifying and mitigating current causes of mis-verification with more diverse, labelled document examples
- Optimise prompts and tune component's values to better represent indicators of higher/lower risk
- Train specialized models for specific banks
- Optimising output depending on how the service ought to be used (as of now it's an executive summary style json)
- Depending on time to invoke/cost restraints, there's a possibility to create a mixture of experts approach with a gating model providing the final risk conclusion and reduce the mis-verification rate/severity
- Appify and containerise the functionality to be invoked as an endpoint

## Limitations

- Currently optimized for English language documents
- Limited to the first 20 pages of a document. This is to minimise cost in the event a document is mis-cliassified as a bank statement
- Performance depends on document quality and format 
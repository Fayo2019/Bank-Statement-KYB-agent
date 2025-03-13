## Bank Statement Verification & Fraud Detection Tool

This python code automates the verification of business bank statements, extracting information and identifying potential fraud signals as part of KYB (Know Your Business) and AML (Anti-Money Laundering) processes for onboarding new business.


## Features

- **Document Classification**: Determines if a document is a business bank statement
   1. Converts PDF to images for GPT-4o analysis
   2. Uses pattern recognition to classify document type

- **Business Details Extraction and Checking**: Extracts business name, address, and account information befor verifying that transaction amounts reconcile with reported balances.
   1. Identifies and extracts structured data from the document
   2. Parses financial transactions and balances
   3. Calculates expected balance changes from transactions
   4. Compares calculated values with reported values

- **Fraud Detection**: After clarifying the document is a financial statement, we ensure it isn't fraudulent. The current checks are:
   - Visual tampering detection (inconsistent fonts, misaligned text, etc.)
   - PDF structure analysis (hidden text, overlays, suspicious modifications)
   - Template placeholder detection
   - Financial inconsistency detection

   1. Visual analysis: Examines document for visual anomalies
   2. Structural analysis: Examines PDF objects for suspicious elements
   3. Financial analysis: Flags unexplained discrepancies

- **Risk Assessment**
   - Calculates an overall fraud risk score
   - Categorizes risk level (Minimal, Low, Medium, High)
   - Provides specific risk factors
   - Code returns a summary report in the console and a JSON analysis file (in the directory of the pdf)


## Setup

1. Ensure you're using python 3.12 in your interpreter (this code can also be ran in a venv instead of the base machine to fix the python version easily).

2. Install Python dependencies: use terminal command 'pip install -r requirements.txt'.

3. Install Poppler (required for pdf2image):
   - macOS: `brew install poppler`
   - Ubuntu/Debian: `apt-get install poppler-utils`
   - Windows: [Download binaries](https://github.com/oschwartz10612/poppler-windows/releases/)

4. Create a .env file in the root directory of the format: 
'''
OPENAI_API_KEY=<your-openai-key>
'''


## Usage

Run the tool on any PDF document from the terminal: 
1. cd to the root directory
2. Use the command 'python src/main.py path/to/bank_statement.pdf'


## Extending the Tool

This MVP can be extended in several ways:
- Identifying and mitigating current causes of mis-verification with more diverse, labelled examples
- Optimise prompts and scoring values to better represent indicators of higher/lower risk
- Train specialized models for specific banks
- Optimising output depending on how the service ought to be used
- Appify and containerise the functionality to be invoked as an endpoint
- split main.py into multiple files for ease of finding the code for functionalities in building later versions.


## Limitations

- Currently optimized for English language documents
- Limited to the first 20 pages of a document. This is to minimise cost in the event a document is mis-cliassified as a bank statement.
- Requires an internet connection for OpenAI API access
- Performance depends on document quality and format 
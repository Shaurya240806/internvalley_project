from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

out_file = 'project_submission.pdf'

c = canvas.Canvas(out_file, pagesize=A4)
W, H = A4

c.setTitle('CypherVault - Secure Image Encryption')
c.setAuthor('Shaurya')

c.setFont('Helvetica-Bold', 22)
c.drawString(50, H - 60, 'CypherVault - Secure Image Encryption')

c.setFont('Helvetica-Bold', 16)
c.drawString(50, H - 110, 'Project Overview')

c.setFont('Helvetica', 12)
text = (
    'This project is a Flask-based secure image encryption system that demonstrates '
    'hybrid cryptography using AES-256-GCM for image encryption and RSA-OAEP for '
    'wrapping the AES key. It is designed for secure storage and transfer of sensitive '
    'image content through a web application.'
)
for i, line in enumerate([text[:92], text[92:184], text[184:]]):
    c.drawString(50, H - (138 + i * 18), line)

c.setFont('Helvetica-Bold', 16)
c.drawString(50, H - 210, 'Key Features')
c.setFont('Helvetica', 12)
features = [
    '- AES-256-GCM encrypted image handling',
    '- RSA key wrapping and secure transfer model',
    '- Flask web app with dashboard and UI flow',
    '- SQLAlchemy database models and secure password hashing',
    '- Security headers and validation for file handling',
    '- Project testing with pytest (19 tests passing)',
]
y = H - 240
for item in features:
    c.drawString(50, y, item)
    y -= 20

c.setFont('Helvetica-Bold', 16)
c.drawString(50, y - 25, 'Technology Stack')
c.setFont('Helvetica', 12)
stack = [
    '- Python 3.14',
    '- Flask, Flask-SQLAlchemy, Flask-Login, Flask-WTF, Flask-Limiter',
    '- cryptography, PyCryptodome, Pillow',
    '- SQLite database and HTML/CSS/JS frontend',
]
y -= 55
for item in stack:
    c.drawString(50, y, item)
    y -= 20

c.setFont('Helvetica-Bold', 16)
c.drawString(50, y - 25, 'Validation')
c.setFont('Helvetica', 12)
c.drawString(50, y - 55, 'The project was verified locally with pytest and responded successfully at http://127.0.0.1:5000')
c.drawString(50, y - 73, 'with HTTP 200. The health endpoint returned status ok and database ok.')

c.setFont('Helvetica-Bold', 16)
c.drawString(50, y - 105, 'Submission Summary')
c.setFont('Helvetica', 12)
c.drawString(50, y - 133, 'This project demonstrates secure image encryption, secure key management,')
c.drawString(50, y - 151, 'and a web-based interface suitable for academic submission and presentation.')

c.save()
print(f'Created: {out_file}')

VERIFICATION_EMAIL_SUBJECT = "Web3Bridge Student Portal — Verify Your Email"

VERIFICATION_EMAIL_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Email Verification</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            background-color: #f8f9fa;
            color: #333;
            margin: 0;
            padding: 0;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #fff;
            border-radius: 10px;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
        }}
        h1 {{
            color: #007bff;
        }}
        p {{
            line-height: 1.6;
            margin-bottom: 15px;
        }}
        .code {{
            display: inline-block;
            padding: 16px 32px;
            background-color: #f0f4ff;
            color: #007bff;
            font-size: 32px;
            font-weight: bold;
            letter-spacing: 8px;
            border-radius: 8px;
            border: 2px dashed #007bff;
            margin: 10px 0;
        }}
        .note {{
            font-size: 0.9rem;
            color: #666;
            margin-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Verify Your Email</h1>
        <p>Hi {name},</p>
        <p>Your account has been activated successfully! To complete the setup,
           please verify your email address by entering the code below:</p>
        <p style="text-align: center;">
            <span class="code">{code}</span>
        </p>
        <p class="note">
            This code expires in 30 minutes. If it expires, you can request a new one
            from the portal.
        </p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
        <p>With Love,</p>
        <p>The Web3Bridge Team</p>
    </div>
</body>
</html>
"""


def render_verification_email(*, name: str, code: str) -> tuple[str, str]:
    """Return (subject, html_body) for the email verification email."""
    html_body = VERIFICATION_EMAIL_HTML.format(name=name, code=code)
    return VERIFICATION_EMAIL_SUBJECT, html_body

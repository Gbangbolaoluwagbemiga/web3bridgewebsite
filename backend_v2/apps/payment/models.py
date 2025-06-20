import string
import secrets


from django.db import models

# Models


# Payment

class Payment(models.Model):
    name = models.CharField(max_length=127, blank=True, null=True)
    email = models.EmailField(max_length=127, unique=False)
    phone_number = models.CharField(max_length=32, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, blank=True, null=True)
    status = models.BooleanField()
    transaction_id = models.CharField(max_length=50, unique=True)
    transaction_ref = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payment'
        managed = False
        indexes = [
            models.Index(fields=['email'], name='payment_email_idx'),
            models.Index(fields=['transaction_id'],
                         name='payment_transaction_id_idx'),
            models.Index(fields=['transaction_ref'],
                         name='payment_transaction_ref_idx'),
        ]

    def __str__(self):
        return f"< {type(self).__name__} : ({self.transaction_id}) >"


# Discount Code

class DiscountCode(models.Model):
    code = models.CharField(max_length=16, unique=True)
    is_used = models.BooleanField(default=False)
    claimant = models.EmailField(max_length=127, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, help_text="Discount percentage (0-100)")

    @classmethod
    def generate_code(cls, length=5):
        while True:
            alphanum = string.ascii_uppercase + string.digits
            code = 'WEB3BRIDGE' + '-' + \
                ''.join(secrets.choice(alphanum) for _ in range(length))

            if not cls.objects.filter(code=code).exists():
                return code

    def __str__(self):
        return f"< {type(self).__name__} : ({self.created_at}) >"

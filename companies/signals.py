from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import (
    Company,
    CompanyModule,
    CompanySettings,
    Module,
)


@receiver(post_save, sender=Company)
def create_company_configuration(
    sender,
    instance,
    created,
    **kwargs,
):
    if not created:
        return

    CompanySettings.objects.get_or_create(
        company=instance,
    )

    active_modules = Module.objects.filter(
        is_active=True,
    )

    CompanyModule.objects.bulk_create(
        [
            CompanyModule(
                company=instance,
                module=module,
                enabled=module.default_enabled,
            )
            for module in active_modules
        ],
        ignore_conflicts=True,
    )


@receiver(post_save, sender=Module)
def assign_module_to_existing_companies(
    sender,
    instance,
    created,
    **kwargs,
):
    if not created:
        return

    CompanyModule.objects.bulk_create(
        [
            CompanyModule(
                company=company,
                module=instance,
                enabled=instance.default_enabled,
            )
            for company in Company.objects.all()
        ],
        ignore_conflicts=True,
    )
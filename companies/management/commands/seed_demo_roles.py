from django.core.management.base import (
    BaseCommand,
    CommandError,
)
from django.db import transaction

from accounts.models import User
from branches.models import (
    Branch,
    BranchMembership,
)
from companies.models import (
    Company,
    CompanyMembership,
)

DEMO_USERS = [
    {
        "email": "owner@skinlab.com",
        "first_name": "Olivia",
        "last_name": "Propietaria",
        "role": CompanyMembership.Role.OWNER,
        "branch_codes": [],
        "default_branch_code": None,
    },
    {
        "email": "admin.branch@skinlab.com",
        "first_name": "Andrea",
        "last_name": "Administradora",
        "role": CompanyMembership.Role.ADMIN,
        "branch_codes": ["PRINCIPAL"],
        "default_branch_code": "PRINCIPAL",
    },
    {
        "email": "manager@skinlab.com",
        "first_name": "Manuel",
        "last_name": "Encargado",
        "role": CompanyMembership.Role.MANAGER,
        "branch_codes": ["ZONA10"],
        "default_branch_code": "ZONA10",
    },
    {
        "email": "cashier@skinlab.com",
        "first_name": "Carla",
        "last_name": "Cajera",
        "role": CompanyMembership.Role.CASHIER,
        "branch_codes": ["ZONA10"],
        "default_branch_code": "ZONA10",
    },
    {
        "email": "seller@skinlab.com",
        "first_name": "Samuel",
        "last_name": "Vendedor",
        "role": CompanyMembership.Role.SELLER,
        "branch_codes": ["ANTIGUA"],
        "default_branch_code": "ANTIGUA",
    },
    {
        "email": "warehouse@skinlab.com",
        "first_name": "Walter",
        "last_name": "Bodeguero",
        "role": CompanyMembership.Role.WAREHOUSE,
        "branch_codes": ["PRINCIPAL"],
        "default_branch_code": "PRINCIPAL",
    },
]

class Command(BaseCommand):
    help = (
        "Crea usuarios, roles y asignaciones de sucursales "
        "para probar SellSys."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--company-id",
            required=True,
            help="UUID de la empresa donde se crearán las pruebas.",
        )

        parser.add_argument(
            "--password",
            default="SellSys123!",
            help=(
                "Contraseña asignada a los usuarios demo. "
                "Por defecto: SellSys123!"
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        company_id = options["company_id"]
        password = options["password"]

        try:
            company = Company.objects.get(
                id=company_id,
                is_active=True,
            )
        except Company.DoesNotExist as error:
            raise CommandError(
                "No existe una empresa activa con ese ID."
            ) from error

        branches = self.create_demo_branches(
            company=company,
        )

        for user_data in DEMO_USERS:
            self.create_demo_user(
                company=company,
                branches=branches,
                password=password,
                user_data=user_data,
            )

        self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                "Usuarios demo creados correctamente."
            )
        )

        self.stdout.write(
            f"Empresa: {company.name}"
        )

        self.stdout.write(
            f"Contraseña común: {password}"
        )

        self.stdout.write("")

        for user_data in DEMO_USERS:
            self.stdout.write(
                (
                    f"{user_data['email']} "
                    f"→ {user_data['role']}"
                )
            )

    def create_demo_branches(
        self,
        company,
    ):
        branch_definitions = [
            {
                "code": "PRINCIPAL",
                "name": "Sucursal principal",
                "address": "Ciudad de Guatemala",
                "is_main": True,
            },
            {
                "code": "ZONA10",
                "name": "Sucursal Zona 10",
                "address": "Zona 10, Ciudad de Guatemala",
                "is_main": False,
            },
            {
                "code": "ANTIGUA",
                "name": "Sucursal Antigua",
                "address": "Antigua Guatemala",
                "is_main": False,
            },
        ]

        branches = {}

        for branch_data in branch_definitions:
            branch, created = Branch.objects.update_or_create(
                company=company,
                code=branch_data["code"],
                defaults={
                    "name": branch_data["name"],
                    "address": branch_data["address"],
                    "is_main": branch_data["is_main"],
                    "is_active": True,
                },
            )

            branches[branch.code] = branch

            action = (
                "Creada"
                if created
                else "Actualizada"
            )

            self.stdout.write(
                f"{action} sucursal: {branch.name}"
            )

        return branches

    def create_demo_user(
        self,
        company,
        branches,
        password,
        user_data,
    ):
        user, user_created = User.objects.get_or_create(
            email=user_data["email"],
            defaults={
                "first_name": user_data["first_name"],
                "last_name": user_data["last_name"],
                "is_active": True,
            },
        )

        user.first_name = user_data["first_name"]
        user.last_name = user_data["last_name"]
        user.is_active = True
        user.set_password(password)

        user.save(
            update_fields=[
                "first_name",
                "last_name",
                "is_active",
                "password",
            ]
        )

        membership, membership_created = (
            CompanyMembership.objects.update_or_create(
                company=company,
                user=user,
                defaults={
                    "role": user_data["role"],
                    "is_active": True,
                },
            )
        )

        self.configure_branch_assignments(
            membership=membership,
            branches=branches,
            branch_codes=user_data["branch_codes"],
            default_branch_code=(
                user_data["default_branch_code"]
            ),
        )

        user_action = (
            "Creado"
            if user_created
            else "Actualizado"
        )

        membership_action = (
            "creada"
            if membership_created
            else "actualizada"
        )

        self.stdout.write(
            (
                f"{user_action}: {user.email} | "
                f"membresía {membership_action} | "
                f"rol {membership.role}"
            )
        )

    def configure_branch_assignments(
        self,
        membership,
        branches,
        branch_codes,
        default_branch_code,
    ):
        """
         * OWNER y ADMIN no necesitan BranchMembership.
         * El endpoint de contexto les proporciona todas las
         * sucursales activas de la empresa.
         """
        if membership.role == CompanyMembership.Role.OWNER:
            BranchMembership.objects.filter(
                company_membership=membership,
            ).delete()

            return

        selected_branches = [
            branches[code]
            for code in branch_codes
        ]

        BranchMembership.objects.filter(
            company_membership=membership,
        ).exclude(
            branch__in=selected_branches,
        ).delete()

        """ 
         * Primero quitamos cualquier predeterminada para
         * respetar la restricción de una sola por usuario.
        """
        BranchMembership.objects.filter(
            company_membership=membership,
        ).update(
            is_default=False,
        )

        assignments = {}

        for branch in selected_branches:
            assignment, _ = (
                BranchMembership.objects.update_or_create(
                    company_membership=membership,
                    branch=branch,
                    defaults={
                        "is_default": False,
                        "is_active": True,
                    },
                )
            )

            assignments[branch.code] = assignment

        if default_branch_code:
            default_assignment = assignments[
                default_branch_code
            ]

            default_assignment.is_default = True
            default_assignment.is_active = True

            default_assignment.save(
                update_fields=[
                    "is_default",
                    "is_active",
                    "updated_at",
                ]
            )
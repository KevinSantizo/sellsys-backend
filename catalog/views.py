from rest_framework.viewsets import ModelViewSet
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import (
    OrderingFilter,
    SearchFilter,
)
from companies.mixins import CompanyAccessMixin
from .models import Brand, Category, Product, UnitOfMeasure
from .serializers import (
    BrandDetailSerializer,
    BrandListSerializer,
    CategoryDetailSerializer,
    CategoryListSerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    UnitOfMeasureDetailSerializer,
    UnitOfMeasureListSerializer,
)

from .pagination import ProductPagination
from decimal import Decimal
from django.db.models import (
    DecimalField,
    OuterRef,
    Subquery,
    Value,
)
from django.db.models.functions import Coalesce
from inventory.models import ProductStock
from rest_framework.exceptions import ValidationError
from common.access import validate_company_branch_access

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from catalog.services.cloudinary_service import (
    upload_product_image,
)

class CatalogBaseViewSet(
    CompanyAccessMixin,
    ModelViewSet,
):
    module_code = "CATALOG"

    def get_base_queryset(self, model):
        if self.should_return_empty_queryset():
            return model.objects.none()

        queryset = model.objects.filter(
            company__memberships__user=(
                self.request.user
            ),
            company__memberships__is_active=True,
            company__is_active=True,
            company__company_modules__module__code=(
                self.module_code
            ),
            company__company_modules__module__is_active=True,
            company__company_modules__enabled=True,
        ).distinct()

        return self.filter_by_company(queryset)

    def get_object(self):
        instance = super().get_object()

        self.ensure_module_enabled(
            instance.company,
            self.module_code,
        )

        return instance

    def perform_create(self, serializer):
        company = serializer.validated_data["company"]

        self.ensure_company_manager(company)

        self.ensure_module_enabled(
            company,
            self.module_code,
        )

        serializer.save()

    def perform_update(self, serializer):
        company = serializer.instance.company

        self.ensure_company_manager(company)

        self.ensure_module_enabled(
            company,
            self.module_code,
        )

        serializer.save()

    def perform_destroy(self, instance):
        self.ensure_company_manager(
            instance.company,
        )

        self.ensure_module_enabled(
            instance.company,
            self.module_code,
        )

        instance.delete()


class CategoryViewSet(CatalogBaseViewSet):
    pagination_class = ProductPagination
    filter_backends = (
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    )

    filterset_fields = (
        "parent",
        "is_active",
    )

    search_fields = (
        "name",
        "description",
        "parent__name",
    )

    ordering_fields = (
        "name",
        "created_at",
        "updated_at",
    )

    ordering = ("name",)

    def get_queryset(self):
        queryset = self.get_base_queryset(
            Category
        ).select_related(
            "company",
            "parent",
        )

        if self.action == "retrieve":
            queryset = queryset.prefetch_related(
                "children"
            )

        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return CategoryListSerializer

        return CategoryDetailSerializer


class BrandViewSet(CatalogBaseViewSet):
    pagination_class = ProductPagination

    filter_backends = (
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    )

    filterset_fields = (
        "is_active",
    )

    search_fields = (
        "name",
        "description",
    )

    ordering_fields = (
        "name",
        "created_at",
        "updated_at",
    )

    ordering = ("name",)

    def get_queryset(self):
        return self.get_base_queryset(
            Brand
        ).select_related(
            "company"
        )

    def get_serializer_class(self):
        if self.action == "list":
            return BrandListSerializer

        return BrandDetailSerializer


class UnitOfMeasureViewSet(CatalogBaseViewSet):
    pagination_class = ProductPagination

    filter_backends = (
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    )

    filterset_fields = (
        "unit_type",
        "allows_decimal",
        "is_active",
    )

    search_fields = (
        "name",
        "symbol",
    )

    ordering_fields = (
        "name",
        "symbol",
        "unit_type",
        "created_at",
        "updated_at",
    )

    ordering = ("name",)

    def get_queryset(self):
        return self.get_base_queryset(
            UnitOfMeasure
        ).select_related(
            "company"
        )

    def get_serializer_class(self):
        if self.action == "list":
            return UnitOfMeasureListSerializer

        return UnitOfMeasureDetailSerializer


class ProductViewSet(CatalogBaseViewSet):
    pagination_class = ProductPagination
    filter_backends = (
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    )

    filterset_fields = (
        "product_type",
        "category",
        "brand",
        "track_inventory",
        "is_active",
    )

    search_fields = (
        "name",
        "sku",
        "barcode",
        "description",
    )

    ordering_fields = (
        "name",
        "sku",
        "cost_price",
        "sale_price",
        "created_at",
    )

    ordering = ("-created_at","-id",)

    def get_queryset(self):
        queryset = (
            self.get_base_queryset(Product)
            .select_related(
                "company",
                "category",
                "brand",
                "base_unit",
            )
        )

        company_id = self.request.query_params.get("company_id")
        branch_id = self.request.query_params.get("branch_id")

        stock_output_field = DecimalField(
            max_digits=14,
            decimal_places=3,
        )

        if branch_id:
            if not company_id:
                raise ValidationError({
                    "company_id": (
                        "Debes enviar company_id "
                        "para consultar inventario por sucursal."
                    )
                })

            validate_company_branch_access(
                self.request.user,
                company_id,
                branch_id,
            )

            stock_subquery = (
                ProductStock.objects
                .filter(
                    company_id=company_id,
                    branch_id=branch_id,
                    product_id=OuterRef("pk"),
                )
                .values("quantity")[:1]
            )

            queryset = queryset.annotate(
                current_stock=Coalesce(
                    Subquery(
                        stock_subquery,
                        output_field=stock_output_field,
                    ),
                    Value(
                        Decimal("0.000"),
                    ),
                    output_field=stock_output_field,
                )
            )
        else:
            queryset = queryset.annotate(
                current_stock=Value(
                    Decimal("0.000"),
                    output_field=stock_output_field,
                )
            )

        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return ProductListSerializer

        return ProductDetailSerializer


    def perform_create(self, serializer):
        company = serializer.validated_data["company"]
        branch_id = serializer.validated_data.get("branch_id")

        print(
            "IMAGE URL:",
            serializer.validated_data.get("image_url"),
        )

        print(
            "IMAGE PUBLIC ID:",
            serializer.validated_data.get("image_public_id"),
        )

        print(
            "VALIDATED DATA:",
            serializer.validated_data,
        )


        if branch_id:
            validate_company_branch_access(
                self.request.user,
                company.id,
                branch_id,
            )

        super().perform_create(serializer)

    @action(
        detail=False,
        methods=["post"],
        url_path="upload-image",
    )
    def upload_image(
            self,
            request,
    ):
        image = request.FILES.get(
            "image"
        )

        if not image:
            return Response(
                {
                    "detail": (
                        "Debes enviar una imagen."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not image.content_type.startswith(
                "image/"
        ):
            return Response(
                {
                    "detail": (
                        "El archivo enviado "
                        "no es una imagen válida."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = (
                upload_product_image(
                    image
                )
            )

            return Response(
                result,
                status=status.HTTP_200_OK,
            )

        except Exception:
            return Response(
                {
                    "detail": (
                        "No se pudo subir "
                        "la imagen."
                    )
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
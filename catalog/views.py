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

class CatalogBaseViewSet(
    CompanyAccessMixin,
    ModelViewSet,
):
    module_code = "CATALOG"

    def get_base_queryset(self, model):
        queryset = model.objects.filter(
            company__memberships__user=self.request.user,
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
    def get_queryset(self):
        queryset = self.get_base_queryset(
            Category
        ).select_related("company", "parent")

        if self.action == "retrieve":
            queryset = queryset.prefetch_related(
                "children"
            )

        return queryset.order_by("name")

    def get_serializer_class(self):
        if self.action == "list":
            return CategoryListSerializer

        return CategoryDetailSerializer


class BrandViewSet(CatalogBaseViewSet):
    def get_queryset(self):
        return self.get_base_queryset(
            Brand
        ).select_related(
            "company"
        ).order_by("name")

    def get_serializer_class(self):
        if self.action == "list":
            return BrandListSerializer

        return BrandDetailSerializer


class UnitOfMeasureViewSet(CatalogBaseViewSet):
    def get_queryset(self):
        return self.get_base_queryset(
            UnitOfMeasure
        ).select_related(
            "company"
        ).order_by("name")

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

        return queryset.order_by( "-created_at", "-id",)

    def get_serializer_class(self):
        if self.action == "list":
            return ProductListSerializer

        return ProductDetailSerializer
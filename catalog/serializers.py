from rest_framework import serializers

from common.serializers import CompanyOwnedModelSerializer

from .models import Brand, Category, Product, UnitOfMeasure


class CategorySummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = (
            'id',
            'name',
            'is_active',
        )

        read_only_fields = fields


class CategoryListSerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(
        source='parent.name',
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = Category
        fields = (
            'id',
            'name',
            'parent_name',
            'is_active',
        )

        read_only_fields = fields


class CategoryDetailSerializer(
    CompanyOwnedModelSerializer
):
    parent_id = serializers.PrimaryKeyRelatedField(
        source='parent',
        queryset=Category.objects.filter(is_active=True),
        required=False,
        allow_null=True,
        write_only=True,
    )

    parent = CategorySummarySerializer(
        read_only=True,
    )

    children = CategorySummarySerializer(
        many=True,
        read_only=True,
    )

    class Meta:
        model = Category
        fields = (
            'id',
            'company_id',
            'name',
            'description',
            'parent_id',
            'parent',
            'children',
            'is_active',
            'created_at',
            'updated_at',
        )

        read_only_fields = (
            'id',
            'parent',
            'children',
            'created_at',
            'updated_at',
        )

    def validate(self, attrs):
        attrs = super().validate(attrs)

        parent = attrs.get('parent')

        if parent is None:
            return attrs

        company = attrs.get('company')

        if self.instance:
            company = self.instance.company

        if parent.company_id != company.id:
            raise serializers.ValidationError({
                'parent_id': (
                    'La categoría padre no pertenece '
                    'a la empresa seleccionada.'
                ),
            })

        if (
            self.instance
            and parent.id == self.instance.id
        ):
            raise serializers.ValidationError({
                'parent_id': (
                    'Una categoría no puede ser '
                    'su propio padre.'
                ),
            })

        current_parent = parent

        while current_parent is not None:
            if (
                self.instance
                and current_parent.id == self.instance.id
            ):
                raise serializers.ValidationError({
                    'parent_id': (
                        'La categoría seleccionada produciría '
                        'una relación circular.'
                    ),
                })

            current_parent = current_parent.parent

        return attrs


class BrandListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = (
            'id',
            'name',
            'is_active',
        )

        read_only_fields = fields


class BrandDetailSerializer(
    CompanyOwnedModelSerializer
):
    class Meta:
        model = Brand
        fields = (
            'id',
            'company_id',
            'name',
            'description',
            'is_active',
            'created_at',
            'updated_at',
        )

        read_only_fields = (
            'id',
            'created_at',
            'updated_at',
        )


class UnitOfMeasureListSerializer(
    serializers.ModelSerializer
):
    unit_type_display = serializers.CharField(
        source='get_unit_type_display',
        read_only=True,
    )

    class Meta:
        model = UnitOfMeasure
        fields = (
            'id',
            'name',
            'symbol',
            'unit_type',
            'unit_type_display',
            'allows_decimal',
            'is_active',
        )

        read_only_fields = fields


class UnitOfMeasureDetailSerializer(
    CompanyOwnedModelSerializer
):
    unit_type_display = serializers.CharField(
        source='get_unit_type_display',
        read_only=True,
    )

    class Meta:
        model = UnitOfMeasure
        fields = (
            'id',
            'company_id',
            'name',
            'symbol',
            'unit_type',
            'unit_type_display',
            'allows_decimal',
            'is_active',
            'created_at',
            'updated_at',
        )

        read_only_fields = (
            'id',
            'unit_type_display',
            'created_at',
            'updated_at',
        )

class ProductListSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(
        source="company.name",
        read_only=True,
    )

    category_name = serializers.CharField(
        source="category.name",
        read_only=True,
        allow_null=True,
    )

    brand_name = serializers.CharField(
        source="brand.name",
        read_only=True,
        allow_null=True,
    )

    base_unit_symbol = serializers.CharField(
        source="base_unit.symbol",
        read_only=True,
        allow_null=True,
    )

    product_type_display = serializers.CharField(
        source="get_product_type_display",
        read_only=True,
    )

    class Meta:
        model = Product
        fields = (
            "id",
            "company_name",
            "name",
            "sku",
            "barcode",
            "product_type",
            "product_type_display",
            "category_name",
            "brand_name",
            "base_unit_symbol",
            "cost_price",
            "sale_price",
            "track_inventory",
            "is_active",
        )

        read_only_fields = fields


class ProductDetailSerializer(
    CompanyOwnedModelSerializer
):
    company_name = serializers.CharField(
        source="company.name",
        read_only=True,
    )

    category_id = serializers.PrimaryKeyRelatedField(
        source="category",
        queryset=Category.objects.filter(
            is_active=True,
        ),
        required=False,
        allow_null=True,
        write_only=True,
    )

    category = CategorySummarySerializer(
        read_only=True,
    )

    brand_id = serializers.PrimaryKeyRelatedField(
        source="brand",
        queryset=Brand.objects.filter(
            is_active=True,
        ),
        required=False,
        allow_null=True,
        write_only=True,
    )

    brand = BrandListSerializer(
        read_only=True,
    )

    base_unit_id = serializers.PrimaryKeyRelatedField(
        source="base_unit",
        queryset=UnitOfMeasure.objects.filter(
            is_active=True,
        ),
        required=False,
        allow_null=True,
        write_only=True,
    )

    base_unit = UnitOfMeasureListSerializer(
        read_only=True,
    )

    product_type_display = serializers.CharField(
        source="get_product_type_display",
        read_only=True,
    )

    class Meta:
        model = Product
        fields = (
            "id",
            "company_id",
            "company_name",
            "name",
            "description",
            "sku",
            "barcode",
            "product_type",
            "product_type_display",
            "category_id",
            "category",
            "brand_id",
            "brand",
            "base_unit_id",
            "base_unit",
            "cost_price",
            "sale_price",
            "track_inventory",
            "is_active",
            "created_at",
            "updated_at",
        )

        read_only_fields = (
            "id",
            "company_name",
            "product_type_display",
            "category",
            "brand",
            "base_unit",
            "created_at",
            "updated_at",
        )

    def validate_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "El nombre del producto es obligatorio."
            )

        return value

    def validate_sku(self, value):
        value = value.strip().upper()

        if not value:
            raise serializers.ValidationError(
                "El SKU es obligatorio."
            )

        return value

    def validate_barcode(self, value):
        if not value:
            return None

        value = value.strip()

        return value or None

    def validate(self, attrs):
        attrs = super().validate(attrs)

        if self.instance:
            company = self.instance.company
        else:
            company = attrs["company"]

        category = attrs.get(
            "category",
            self.instance.category
            if self.instance
            else None,
        )

        brand = attrs.get(
            "brand",
            self.instance.brand
            if self.instance
            else None,
        )

        base_unit = attrs.get(
            "base_unit",
            self.instance.base_unit
            if self.instance
            else None,
        )

        product_type = attrs.get(
            "product_type",
            self.instance.product_type
            if self.instance
            else Product.ProductType.PRODUCT,
        )

        sku = attrs.get(
            "sku",
            self.instance.sku
            if self.instance
            else None,
        )

        barcode = attrs.get(
            "barcode",
            self.instance.barcode
            if self.instance
            else None,
        )

        errors = {}

        if (
            category
            and category.company_id != company.id
        ):
            errors["category_id"] = (
                "La categoría no pertenece a "
                "la empresa seleccionada."
            )

        if (
            brand
            and brand.company_id != company.id
        ):
            errors["brand_id"] = (
                "La marca no pertenece a "
                "la empresa seleccionada."
            )

        if (
            base_unit
            and base_unit.company_id != company.id
        ):
            errors["base_unit_id"] = (
                "La unidad de medida no pertenece a "
                "la empresa seleccionada."
            )

        if (
            product_type == Product.ProductType.PRODUCT
            and base_unit is None
        ):
            errors["base_unit_id"] = (
                "Los productos físicos deben tener "
                "una unidad de medida base."
            )

        if product_type == Product.ProductType.SERVICE:
            if attrs.get("track_inventory") is True:
                errors["track_inventory"] = (
                    "Un servicio no puede controlar inventario."
                )

            attrs["track_inventory"] = False

        sku_queryset = Product.objects.filter(
            company=company,
            sku__iexact=sku,
        )

        if self.instance:
            sku_queryset = sku_queryset.exclude(
                id=self.instance.id,
            )

        if sku_queryset.exists():
            errors["sku"] = (
                "Ya existe un producto con este SKU "
                "en la empresa."
            )

        if barcode:
            barcode_queryset = Product.objects.filter(
                company=company,
                barcode=barcode,
            )

            if self.instance:
                barcode_queryset = (
                    barcode_queryset.exclude(
                        id=self.instance.id,
                    )
                )

            if barcode_queryset.exists():
                errors["barcode"] = (
                    "Ya existe un producto con este "
                    "código de barras en la empresa."
                )

        if errors:
            raise serializers.ValidationError(errors)

        return attrs
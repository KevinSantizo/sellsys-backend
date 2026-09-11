from django.contrib import admin

from .models import CashRegister, CashSession, CashMovement

# Register your models here.

@admin.register(CashRegister)
class CashRegisterAdmin(admin.ModelAdmin):
    list_display = ( "name", "code", "company", "branch", "is_active", "created_at", )
    list_filter = ( "is_active", "company", "branch", )
    search_fields = ( "name", "code", "company__name", "branch__name", )
    readonly_fields = ( "id", "created_at", "updated_at", )
    ordering = ( "company__name", "branch__name", "name", )


class CashMovementInline(admin.TabularInline):
    model = CashMovement
    extra = 0
    can_delete = False
    show_change_link = True

    fields = ( "direction", "movement_type", "amount", "reference", "created_by", "created_at", )
    readonly_fields = ( "direction", "movement_type", "amount", "reference", "created_by", "created_at", )

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(CashSession)
class CashSessionAdmin(admin.ModelAdmin):
    list_display = ( "cash_register", "company", "branch", "status", "opening_amount", "expected_amount", "counted_amount", "difference", "opened_by", "opened_at", )
    list_filter = ( "status", "company", "branch", "cash_register", )
    search_fields = ( "cash_register__name", "cash_register__code", "company__name", "branch__name", "opened_by__username", )
    readonly_fields = ( "id", "opened_at", "closed_at", "created_at", "updated_at", )
    ordering = ( "-opened_at", )
    inlines = [ CashMovementInline ]


@admin.register(CashMovement)
class CashMovementAdmin(admin.ModelAdmin):
    list_display = ( "movement_type", "direction", "amount", "company", "branch", "cash_session", "reference", "created_by", "created_at", )
    list_filter = ( "direction", "movement_type", "source_type", "company", "branch", )
    search_fields = ( "reference", "notes", "company__name", "branch__name", "cash_session__cash_register__name", )
    readonly_fields = ( "id", "created_at", )
    ordering = ( "-created_at", )
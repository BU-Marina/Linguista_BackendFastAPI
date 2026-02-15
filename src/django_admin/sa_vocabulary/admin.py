"""Vocabulary app admin panel."""

from django.contrib import admin

from sa_core.admin_i18n import I18nTabbedAdmin

from .models import (
    SaAntonym,
    SaCollection,
    SaDefinition,
    SaFavoriteCollection,
    SaFavoriteWord,
    SaForm,
    SaFormGroup,
    SaDerivative,
    SaImageAssociation,
    SaSimilar,
    SaSynonym,
    SaWordType,
    SaUsageExample,
    SaWord,
    SaWordActivityHistory,
    SaWordDefinitions,
    SaWordsFormGroups,
    SaWordsInCollections,
    SaWordTranslation,
    SaWordTranslations,
    SaWordUsageExamples,
    SaQuoteAssociation,
    SaWordImageAssociations,
    SaWordQuoteAssociations,
    SaPremiumRequest,
    SaViewWord,
    SaViewCollection,
    SaCollectionSubscription,
    SaCollectionComment,
    SaWordComment,
    SaWordsSuggestedToCollections,
)


class WordTranslationInline(admin.TabularInline):
    model = SaWordTranslations
    exclude = ('created', 'modified')


class WordFormGroupsInline(admin.TabularInline):
    model = SaWordsFormGroups
    exclude = ('created', 'modified')


class SynonymInline(admin.TabularInline):
    model = SaSynonym
    fk_name = 'to_word'
    exclude = ('created', 'modified')


class AntonymInline(admin.TabularInline):
    model = SaAntonym
    fk_name = 'to_word'
    exclude = ('created', 'modified')


class FormInline(admin.TabularInline):
    model = SaForm
    fk_name = 'to_word'
    exclude = ('created', 'modified')


class DerivativeInLine(admin.TabularInline):
    model = SaDerivative
    fk_name = 'to_word'
    exclude = ('created', 'modified')


class SimilarInline(admin.TabularInline):
    model = SaSimilar
    fk_name = 'to_word'
    exclude = ('created', 'modified')


class WordUsageExamplesInline(admin.TabularInline):
    model = SaWordUsageExamples
    exclude = ('created', 'modified')


class WordDefinitionsInline(admin.TabularInline):
    model = SaWordDefinitions
    exclude = ('created', 'modified')


class WordImageAssociationsInline(admin.TabularInline):
    model = SaWordImageAssociations
    raw_id_fields = ('image',)
    exclude = ('created', 'modified')


@admin.register(SaWord)
class WordAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('text', 'author')}
    list_display = (
        'slug',
        'text',
        'language',
        'author',
        'activity_status',
        'activity_progress',
        'created',
        'modified',
    )
    list_display_links = ('slug',)
    search_fields = ('text', 'author__username', 'id')
    list_filter = ('read_access_level', 'add_access_level')
    inlines = (
        WordFormGroupsInline,
        WordTranslationInline,
        WordUsageExamplesInline,
        WordDefinitionsInline,
        SynonymInline,
        AntonymInline,
        FormInline,
        DerivativeInLine,
        SimilarInline,
        WordImageAssociationsInline,
    )


@admin.register(SaWordActivityHistory)
class WordActivityHistoryAdmin(admin.ModelAdmin):
    pass


@admin.register(SaWordType)
class WordTypeAdmin(I18nTabbedAdmin):
    fieldsets = (
        (
            'Translations',
            {
                'fields': (
                    'name_ru',
                    'name_en',
                )
            },
        ),
        (
            'Other',
            {
                'fields': (
                    'slug',
                    # 'words_count',
                )
            },
        ),
    )

    prepopulated_fields = {'slug': ('name_en',)}
    list_display = ('name', 'slug', 'words_count')
    list_display_links = ('name',)
    search_fields = ('name',)
    readonly_fields = ('created', 'modified')

    @admin.display(description='Name')
    def name(self, obj: SaWordType) -> str:
        return obj.name_en or obj.name_ru or ''

    def save_model(self, request, obj, form, change):
        """Preserve created timestamp when updating."""
        if change and obj.pk:
            # When updating, preserve the original created timestamp
            original = SaWordType.objects.get(pk=obj.pk)
            obj.created = original.created
        super().save_model(request, obj, form, change)


class CollectionWordInLine(admin.TabularInline):
    model = SaWordsInCollections
    exclude = ('created', 'modified')


@admin.register(SaCollection)
class CollectionAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('title', 'author')}
    list_display = ('slug', 'title', 'author', 'words_count')
    list_display_links = ('slug',)
    search_fields = (
        'title',
        'author__username',
    )
    list_filter = ('read_access_level', 'add_access_level')
    inlines = (CollectionWordInLine,)


@admin.register(SaFormGroup)
class FormGroupAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name', 'author')}
    list_display = ('slug', 'name', 'author', 'words_count')
    list_display_links = ('slug',)


@admin.register(SaWordTranslation)
class WordTranslationAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('text', 'author')}
    list_display = ('slug', 'text', 'language', 'words_count')
    list_display_links = ('slug',)
    search_fields = ('text', 'author__username', 'id')


@admin.register(SaUsageExample)
class UsageExampleAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('text', 'author')}
    list_display = ('slug', 'text', 'translation', 'words_count')
    list_display_links = ('slug',)


@admin.register(SaDefinition)
class DefinitionAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('text', 'author')}
    list_display = ('slug', 'text', 'translation', 'words_count')
    list_display_links = ('slug',)


@admin.register(SaImageAssociation)
class ImageAssociationAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'image_url',
        'width',
        'height',
    )
    search_fields = ('wordimageassociations__word__text', 'id')
    ordering = ('-created',)


@admin.register(SaQuoteAssociation)
class QuoteAssociationAdmin(admin.ModelAdmin):
    pass


@admin.register(SaSynonym)
class SynonymAdmin(admin.ModelAdmin):
    list_display = ('from_word', 'to_word', 'note')
    list_display_links = ('from_word',)


@admin.register(SaAntonym)
class AntonymAdmin(admin.ModelAdmin):
    list_display = ('from_word', 'to_word', 'note')
    list_display_links = ('from_word',)


@admin.register(SaForm)
class FormAdmin(admin.ModelAdmin):
    list_display = ('from_word', 'to_word')
    list_display_links = ('from_word',)


@admin.register(SaDerivative)
class DerivativeAdmin(admin.ModelAdmin):
    list_display = ('from_word', 'to_word')
    list_display_links = ('from_word',)


@admin.register(SaSimilar)
class SimilarAdmin(admin.ModelAdmin):
    list_display = ('from_word', 'to_word')
    list_display_links = ('from_word',)


@admin.register(SaFavoriteWord)
class FavoriteWordAdmin(admin.ModelAdmin):
    pass


@admin.register(SaFavoriteCollection)
class FavoriteCollectionAdmin(admin.ModelAdmin):
    pass


@admin.register(SaWordTranslations)
class WordTranslationsAdmin(admin.ModelAdmin):
    pass


@admin.register(SaWordUsageExamples)
class WordUsageExamplesAdmin(admin.ModelAdmin):
    pass


@admin.register(SaWordDefinitions)
class WordDefinitionsAdmin(admin.ModelAdmin):
    pass


@admin.register(SaWordsInCollections)
class WordsInCollectionsAdmin(admin.ModelAdmin):
    pass


@admin.register(SaWordImageAssociations)
class WordImageAssociationsAdmin(admin.ModelAdmin):
    pass


@admin.register(SaWordQuoteAssociations)
class WordQuoteAssociationsAdmin(admin.ModelAdmin):
    pass


@admin.register(SaWordsFormGroups)
class WordsFormGroupsAdmin(admin.ModelAdmin):
    pass


@admin.register(SaPremiumRequest)
class PremiumRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'author', 'word', 'collection', 'request_status')
    list_display_links = ('id',)
    list_filter = ('request_status',)
    search_fields = ('author__username', 'word', 'collection')


@admin.register(SaViewWord)
class ViewWordAdmin(admin.ModelAdmin):
    pass


@admin.register(SaViewCollection)
class ViewCollectionAdmin(admin.ModelAdmin):
    pass


@admin.register(SaCollectionSubscription)
class CollectionSubscriptionAdmin(admin.ModelAdmin):
    pass


@admin.register(SaCollectionComment)
class CollectionCommentAdmin(admin.ModelAdmin):
    pass


@admin.register(SaWordComment)
class WordCommentAdmin(admin.ModelAdmin):
    pass


@admin.register(SaWordsSuggestedToCollections)
class WordsSuggestedToCollectionsAdmin(admin.ModelAdmin):
    pass

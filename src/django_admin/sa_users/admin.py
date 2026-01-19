from django.contrib import admin

from .models import (
    SaUser,
    SaUserSettings,
    SaInterest,
    SaSubscription,
    SaFriend,
    SaFriendRequest,
    SaSocialLink,
    SaCity,
    SaGoal,
    SaGoalMember,
    SaStudyPlan,
    SaStrikeSeriaHistory,
)


class InterestInline(admin.TabularInline):
    model = SaInterest
    exclude = ('created', 'modified')


class SubscriptionInline(admin.TabularInline):
    model = SaSubscription
    fk_name = 'subscriber'
    exclude = ('created', 'modified')


class SocialLinkInline(admin.TabularInline):
    model = SaSocialLink
    exclude = ('created', 'modified')


@admin.register(SaUser)
class SaUserAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'email',
        'username',
        'is_active',
        'is_superuser',
        'is_teacher',
        'subscription_plan',
        'date_joined',
    )
    list_filter = ('is_active', 'is_superuser', 'is_teacher', 'subscription_plan')
    search_fields = ('email', 'username', 'first_name')
    readonly_fields = ('id', 'date_joined', 'last_login', 'last_activity_date')

    fieldsets = (
        (None, {'fields': ('username', 'hashed_password', 'slug')}),
        (
            'Personal info',
            {
                'fields': (
                    'first_name',
                    'email',
                    'gender',
                    'profile_description',
                    'profile_image_url',
                    'profile_header_image_url',
                    'is_teacher',
                    'teaching_goal',
                    'subscription_plan',
                    # 'friends',
                    # 'friend_requests',
                    # 'cities',
                    # 'interests',
                    'strike_status',
                    # 'study_plan',
                    'login_allowed',
                    'onboarding_passed',
                    'is_official',
                )
            },
        ),
        (
            'Permissions',
            {
                'fields': (
                    'is_active',
                    'is_staff',
                    'is_superuser',
                    # 'groups',
                    # 'user_permissions',
                )
            },
        ),
        (
            'Important dates',
            {
                'fields': (
                    'last_login',
                    'last_activity_date',
                    'date_joined',
                )
            },
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': (
                    'username',
                    'email',
                    'password1',
                    'password2',
                ),
            },
        ),
    )

    inlines = (
        InterestInline,
        SocialLinkInline,
        SubscriptionInline,
    )


@admin.register(SaSubscription)
class SaSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'subscriber', 'user', 'enable_notifications')
    list_display_links = ('id',)
    list_filter = ('subscriber', 'user', 'enable_notifications')
    search_fields = ('subscriber__username', 'user__username')


@admin.register(SaFriend)
class SaFriendAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'friend', 'created')
    list_filter = ('user', 'friend')
    search_fields = ('user__username', 'friend__username')
    readonly_fields = ('id', 'created', 'modified')


@admin.register(SaFriendRequest)
class SaFriendRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'requester', 'target', 'created')
    list_filter = ('requester', 'target')
    search_fields = ('requester__username', 'target__username')
    readonly_fields = ('id', 'created', 'modified')


@admin.register(SaInterest)
class SaInterestAdmin(admin.ModelAdmin):
    list_display = ('name', 'author')
    list_display_links = ('name',)
    list_filter = ('author',)


@admin.register(SaCity)
class SaCityAdmin(admin.ModelAdmin):
    list_display = ('name',)
    list_display_links = ('name',)
    search_fields = ('name',)


@admin.register(SaSocialLink)
class SaSocialLinkAdmin(admin.ModelAdmin):
    list_display = ('name', 'link', 'user')
    list_display_links = ('name',)
    list_filter = ('user',)


@admin.register(SaUserSettings)
class SaUserSettingsAdmin(admin.ModelAdmin):
    list_display = ('user',)
    list_display_links = ('user',)
    search_fields = ('user__username',)


@admin.register(SaGoal)
class SaGoalAdmin(admin.ModelAdmin):
    pass


@admin.register(SaGoalMember)
class SaGoalMemberAdmin(admin.ModelAdmin):
    pass


@admin.register(SaStudyPlan)
class SaStudyPlanAdmin(admin.ModelAdmin):
    pass


@admin.register(SaStrikeSeriaHistory)
class SaStrikeSeriaHistoryAdmin(admin.ModelAdmin):
    pass

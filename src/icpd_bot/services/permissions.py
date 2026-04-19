import discord


def member_has_role(interaction: discord.Interaction, role_id: int) -> bool:
    user = interaction.user
    if not isinstance(user, discord.Member):
        return False
    return any(role.id == role_id for role in user.roles)


def member_is_admin(interaction: discord.Interaction) -> bool:
    user = interaction.user
    if not isinstance(user, discord.Member):
        return False
    permissions = user.guild_permissions
    return permissions.administrator

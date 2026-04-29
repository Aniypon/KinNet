from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run Telegram bot for Family Circle."

    def handle(self, *args, **options):
        from bot.bot import main

        main()

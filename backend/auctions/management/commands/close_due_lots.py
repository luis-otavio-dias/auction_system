"""Processa lotes vencidos por comando operacional."""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser

from auctions.services.settlement import settle_due_lots


class Command(BaseCommand):
    """Executa uma varredura de liquidação limitada."""

    help = "Liquida lotes vencidos em uma execução limitada."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--once", action="store_true")

    def handle(self, *args: str, **options: bool) -> None:
        del args, options
        processed = settle_due_lots(batch_size=settings.SETTLEMENT_BATCH_SIZE)
        self.stdout.write(
            self.style.SUCCESS(f"Lotes verificados: {processed}")
        )

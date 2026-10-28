"""Seed reproduzível para demonstrar o fluxo completo do leilão."""

from __future__ import annotations

import os
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING
from unittest.mock import patch
from uuid import NAMESPACE_URL, uuid5

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from django.utils import timezone

from auctions.models import Bid, CatalogItem, Lot, Receipt
from auctions.seed_data import CATALOG_SEED_ITEMS
from auctions.services.bidding import place_bid
from auctions.services.lots import create_lot
from auctions.services.settlement import settle_lot
from users.models import User
from wallet.models import Wallet, WalletTransaction
from wallet.services import deposit, release

if TYPE_CHECKING:
    from datetime import datetime

DEMO_SELLER_EMAIL = "leiloeiro@demo.com"
DEMO_BIDDER_EMAILS = ("cliente1@demo.com", "cliente2@demo.com")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "demo-password-123")
DEMO_STARTING_BID = Decimal("500.00")
DEMO_MIN_INCREMENT = Decimal("25.00")
DEMO_DEPOSIT = Decimal("10000.00")
DEMO_REQUIRED_BIDS = 2


class Command(BaseCommand):
    """Cria contas, carteiras e lotes de demonstração."""

    help = "Cria dados completos de demonstração sem depender da API externa."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--reset", action="store_true")
        parser.add_argument("--new-live", action="store_true")

    @transaction.atomic
    def handle(self, *args: str, **options: bool) -> str:
        del args
        if options.get("reset", False):
            self._reset_demo_data()
        seller = self._get_user(
            DEMO_SELLER_EMAIL, User.Role.SELLER, "Leiloeiro Demonstração"
        )
        bidders = tuple(
            self._get_user(
                email, User.Role.BIDDER, f"Cliente de demonstração {index}"
            )
            for index, email in enumerate(DEMO_BIDDER_EMAILS, start=1)
        )
        items = self._seed_catalog()
        self._seed_deposits(bidders)
        live = self._seed_live_lot(
            seller, bidders, items[0], force=options.get("new_live", False)
        )
        self._ensure_live_bids(live, bidders)
        scheduled = self._seed_scheduled_lot(seller, items[1])
        closed = self._seed_closed_lot(seller, bidders, items[2])
        self.stdout.write(
            self.style.SUCCESS(
                f"Seed concluído: {seller.email}, {len(bidders)} licitantes, "
                "lotes ao vivo/agendado/encerrado "
                f"{live.code}/{scheduled.code}/{closed.code}."
            )
        )
        return ""

    def _get_user(self, email: str, role: str, full_name: str) -> User:
        user, _created = User.objects.get_or_create(
            email=email,
            defaults={"role": role, "full_name": full_name},
        )
        user.set_password(DEMO_PASSWORD)
        user.save(update_fields=("password",))
        return user

    def _seed_catalog(self) -> tuple[CatalogItem, ...]:
        items: list[CatalogItem] = []
        for seed in CATALOG_SEED_ITEMS:
            fields = {
                "title": seed.title,
                "description": seed.description,
                "image_url": seed.image_url,
                "thumbnail_url": seed.thumbnail_url,
                "source_url": seed.source_url,
                "category": seed.category,
                "attributes": dict(seed.attributes),
                "raw_payload": dict(seed.raw_payload),
            }
            item, created = CatalogItem.objects.get_or_create(
                source=seed.source,
                external_id=seed.external_id,
                defaults=fields,
            )
            if not created:
                # Mantém o espelho local alinhado às fixtures (ex.: imagens
                # empacotadas) sem criar um novo snapshot.
                CatalogItem.objects.filter(pk=item.pk).update(**fields)
                item.refresh_from_db()
            items.append(item)
        return tuple(items)

    def _seed_deposits(self, bidders: tuple[User, ...]) -> None:
        for bidder in bidders:
            deposit(
                Wallet.objects.get(user=bidder).pk,
                DEMO_DEPOSIT,
                idempotency_key=f"seed-demo:{bidder.pk}:deposit-v1",
                description="Depósito de demonstração",
            )

    def _create_lot(
        self,
        seller: User,
        item: CatalogItem,
        *,
        starts_at: datetime,
        ends_at: datetime,
        clock_now: datetime,
    ) -> Lot:
        with patch(
            "auctions.services.lots.timezone.now", return_value=clock_now
        ):
            return create_lot(
                seller=seller,
                catalog_item=item,
                starts_at=starts_at,
                ends_at=ends_at,
                starting_bid=DEMO_STARTING_BID,
                min_increment=DEMO_MIN_INCREMENT,
                cache_image=False,
            )

    def _place_demo_bids(self, lot: Lot, bidders: tuple[User, ...]) -> None:
        existing_count = lot.bids_count
        for bidder in bidders:
            if existing_count >= DEMO_REQUIRED_BIDS:
                return
            if lot.current_winner_id == bidder.pk:
                continue
            client_id = uuid5(
                NAMESPACE_URL, f"seed-demo:{lot.pk}:{bidder.pk}:bid-v1"
            )
            place_bid(
                lot_id=lot.pk,
                bidder=bidder,
                amount=lot.minimum_bid,
                client_bid_id=client_id,
            )
            lot.refresh_from_db()
            existing_count = lot.bids_count

    def _seed_live_lot(
        self,
        seller: User,
        bidders: tuple[User, ...],
        item: CatalogItem,
        *,
        force: bool,
    ) -> Lot:
        existing = (
            Lot.objects.filter(
                seller=seller,
                source=item.source,
                external_id=item.external_id,
                settled_at__isnull=True,
                cancelled_at__isnull=True,
                starts_at__lte=timezone.now(),
                ends_at__gt=timezone.now(),
            )
            .order_by("created_at")
            .first()
        )
        if existing is not None and not force:
            lot = existing
        else:
            now = timezone.now()
            lot = self._create_lot(
                seller,
                item,
                starts_at=now - timedelta(minutes=5),
                ends_at=now + timedelta(days=3),
                clock_now=now,
            )
        self._place_demo_bids(lot, bidders)
        lot.refresh_from_db()
        return lot

    def _ensure_live_bids(self, lot: Lot, bidders: tuple[User, ...]) -> None:
        lot.refresh_from_db()
        if lot.status_at(timezone.now()) != Lot.Status.LIVE:
            return
        self._place_demo_bids(lot, bidders)
        lot.refresh_from_db()

    def _seed_scheduled_lot(self, seller: User, item: CatalogItem) -> Lot:
        existing = Lot.objects.filter(
            seller=seller,
            source=item.source,
            external_id=item.external_id,
            starts_at__gt=timezone.now(),
            settled_at__isnull=True,
            cancelled_at__isnull=True,
        ).first()
        if existing is not None:
            return existing
        now = timezone.now()
        return self._create_lot(
            seller,
            item,
            starts_at=now + timedelta(days=1),
            ends_at=now + timedelta(days=4),
            clock_now=now,
        )

    def _seed_closed_lot(
        self, seller: User, bidders: tuple[User, ...], item: CatalogItem
    ) -> Lot:
        existing = Lot.objects.filter(
            seller=seller, source=item.source, external_id=item.external_id
        ).first()
        if existing is not None:
            if existing.settled_at is not None:
                return existing
            lot = existing
        else:
            now = timezone.now()
            ends_at = now - timedelta(hours=1)
            clock_now = now - timedelta(hours=2)
            lot = self._create_lot(
                seller,
                item,
                starts_at=now - timedelta(days=2),
                ends_at=ends_at,
                clock_now=clock_now,
            )
        bid_clock = lot.ends_at - timedelta(minutes=1)
        for bidder in bidders:
            if (
                lot.bids_count >= DEMO_REQUIRED_BIDS
                or lot.current_winner_id == bidder.pk
            ):
                continue
            with patch(
                "auctions.services.bidding.timezone.now",
                return_value=bid_clock,
            ):
                place_bid(lot_id=lot.pk, bidder=bidder, amount=lot.minimum_bid)
            lot.refresh_from_db()
        settle_lot(lot.pk)
        lot.refresh_from_db()
        return lot

    def _reset_demo_data(self) -> None:
        demo_users = User.objects.filter(
            email__in=(DEMO_SELLER_EMAIL, *DEMO_BIDDER_EMAILS)
        )
        demo_bidder_ids = tuple(demo_users.values_list("pk", flat=True))
        demo_lots = Lot.objects.filter(seller__in=demo_users)
        demo_bids = Bid.objects.filter(lot__in=demo_lots)
        demo_lot_ids = tuple(demo_lots.values_list("pk", flat=True))
        for lot in demo_lots.select_related("current_winner"):
            if (
                lot.current_winner_id is None
                or lot.current_bid is None
                or lot.settled_at is not None
                or lot.cancelled_at is not None
            ):
                continue
            last_bid = Bid.objects.filter(
                lot=lot, sequence=lot.bids_count
            ).first()
            if last_bid is None:
                continue
            release(
                Wallet.objects.get(user_id=lot.current_winner_id).pk,
                lot.current_bid,
                reference_id=last_bid.pk,
                idempotency_key=f"seed-reset:{lot.pk.hex[:8]}:{last_bid.pk.hex[:8]}",
            )
        WalletTransaction.objects.filter(
            wallet__user_id__in=demo_bidder_ids,
            type=WalletTransaction.Type.DEPOSIT,
            idempotency_key__startswith="seed-demo:",
        ).delete()
        WalletTransaction.objects.filter(
            reference_id__in=demo_bids.values_list("pk", flat=True)
        ).delete()
        WalletTransaction.objects.filter(
            reference_kind=WalletTransaction.ReferenceKind.LOT,
            reference_id__in=demo_lot_ids,
        ).delete()
        Receipt.objects.filter(lot__in=demo_lots).delete()
        demo_bids.delete()
        demo_lots.delete()
        wallets = Wallet.objects.filter(user__in=demo_users)
        wallets.update(balance=Decimal("0.00"), committed=Decimal("0.00"))

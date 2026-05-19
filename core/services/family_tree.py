from dataclasses import dataclass

from django.db import transaction

from core.models import Family, FamilyMember


class FamilyTreeValidationError(ValueError):
	def __init__(self, message, code="invalid"):
		super().__init__(message)
		self.message = message
		self.code = code


@dataclass(frozen=True)
class TreeIssue:
	code: str
	message: str
	member_id: int | None = None


def _full_name(first_name="", last_name="", middle_name=""):
	return " ".join(part.strip() for part in [last_name, first_name, middle_name] if part and part.strip())


def find_duplicate_member(family, *, first_name, last_name="", middle_name="", birth_date=None):
	query = family.family_members.filter(
		first_name__iexact=(first_name or "").strip(),
		last_name__iexact=(last_name or "").strip(),
		middle_name__iexact=(middle_name or "").strip(),
	)
	if birth_date:
		query = query.filter(birth_date=birth_date)
	return query.first()


def create_member(family, *, first_name, last_name="", middle_name="", relation="", birth_date=None):
	first_name = (first_name or "").strip()
	if not first_name:
		raise FamilyTreeValidationError("Укажите имя родственника.", code="missing_name")

	duplicate = find_duplicate_member(
		family,
		first_name=first_name,
		last_name=last_name,
		middle_name=middle_name,
		birth_date=birth_date,
	)
	if duplicate:
		raise FamilyTreeValidationError(
			f"{duplicate} уже есть в этой семье.",
			code="duplicate_member",
		)

	return FamilyMember.objects.create(
		family=family,
		first_name=first_name,
		last_name=(last_name or "").strip(),
		middle_name=(middle_name or "").strip(),
		relation=(relation or "").strip(),
		birth_date=birth_date,
		display_order=family.family_members.count(),
		in_tree=True,
	)


def _member(family, member_id, field_name="member"):
	try:
		return family.family_members.get(id=member_id)
	except (FamilyMember.DoesNotExist, TypeError, ValueError):
		raise FamilyTreeValidationError("Участник не найден.", code=f"{field_name}_not_found")


def _ancestor_ids(member, *, overrides=None, seen=None):
	overrides = overrides or {}
	seen = seen or set()
	if member.id in seen:
		return seen
	seen.add(member.id)
	parent_ids = overrides.get(member.id, (member.parent1_id, member.parent2_id))
	for parent_id in [pid for pid in parent_ids if pid]:
		parent = FamilyMember.objects.filter(id=parent_id, family=member.family).first()
		if parent:
			_ancestor_ids(parent, overrides=overrides, seen=seen)
	return seen


def _would_create_parent_cycle(child, parent, *, overrides=None):
	return child.id in _ancestor_ids(parent, overrides=overrides, seen=set())


def validate_parent_assignment(child, parent, *, second_parent=None):
	if child.family_id != parent.family_id:
		raise FamilyTreeValidationError("Родитель должен быть из той же семьи.", code="cross_family_parent")
	if child.id == parent.id:
		raise FamilyTreeValidationError("Нельзя указать человека его же родителем.", code="self_parent")
	if second_parent and second_parent.id == parent.id:
		raise FamilyTreeValidationError("Родители не должны совпадать.", code="duplicate_parent")
	if second_parent and child.id == second_parent.id:
		raise FamilyTreeValidationError("Нельзя указать человека его же родителем.", code="self_parent")
	if second_parent and second_parent.family_id != child.family_id:
		raise FamilyTreeValidationError("Родитель должен быть из той же семьи.", code="cross_family_parent")

	next_parent_ids = [parent.id, second_parent.id if second_parent else None]
	if _would_create_parent_cycle(child, parent, overrides={child.id: tuple(next_parent_ids)}):
		raise FamilyTreeValidationError("Так получится цикл: ребёнок станет предком родителя.", code="parent_cycle")
	if second_parent and _would_create_parent_cycle(child, second_parent, overrides={child.id: tuple(next_parent_ids)}):
		raise FamilyTreeValidationError("Так получится цикл: ребёнок станет предком родителя.", code="parent_cycle")


def validate_pair(member_a, member_b):
	if member_a.family_id != member_b.family_id:
		raise FamilyTreeValidationError("Пара должна быть из одной семьи.", code="cross_family_pair")
	if member_a.id == member_b.id:
		raise FamilyTreeValidationError("Нельзя создать пару с самим собой.", code="self_pair")
	if member_a.parent1_id == member_b.id or member_a.parent2_id == member_b.id:
		raise FamilyTreeValidationError("Нельзя создать пару с родителем.", code="parent_pair")
	if member_b.parent1_id == member_a.id or member_b.parent2_id == member_a.id:
		raise FamilyTreeValidationError("Нельзя создать пару с ребёнком.", code="child_pair")
	if member_a.spouse_id and member_a.spouse_id != member_b.id:
		raise FamilyTreeValidationError(f"У {member_a} уже есть супруг.", code="member_a_has_spouse")
	if member_b.spouse_id and member_b.spouse_id != member_a.id:
		raise FamilyTreeValidationError(f"У {member_b} уже есть супруг.", code="member_b_has_spouse")


def restore_tree_snapshot(family, snapshot):
	if not isinstance(snapshot, list):
		raise FamilyTreeValidationError("Некорректный снимок древа.", code="bad_snapshot")

	members = {member.id: member for member in family.family_members.all()}
	allowed_ids = set(members)
	updates = []

	for item in snapshot:
		try:
			member_id = int(item.get("id"))
		except (TypeError, ValueError, AttributeError):
			raise FamilyTreeValidationError("В снимке есть неизвестный участник.", code="bad_snapshot")
		if member_id not in allowed_ids:
			raise FamilyTreeValidationError("В снимке есть участник из другой семьи.", code="cross_family_snapshot")

		def clean_id(value):
			if value in ("", None):
				return None
			try:
				value = int(value)
			except (TypeError, ValueError):
				raise FamilyTreeValidationError("В снимке есть некорректная связь.", code="bad_snapshot")
			if value not in allowed_ids:
				raise FamilyTreeValidationError("В снимке есть связь с другой семьёй.", code="cross_family_snapshot")
			return value

		updates.append(
			(
				member_id,
				clean_id(item.get("parent1")),
				clean_id(item.get("parent2")),
				clean_id(item.get("spouse")),
				bool(item.get("in_tree")),
			)
		)

	for member_id, parent1_id, parent2_id, spouse_id, in_tree in updates:
		member = members[member_id]
		member.parent1_id = parent1_id
		member.parent2_id = parent2_id
		member.spouse_id = spouse_id
		member.in_tree = in_tree
		member.save(update_fields=["parent1", "parent2", "spouse", "in_tree"])


def set_parent_slot(family, *, child_id, parent_id, slot):
	child = _member(family, child_id, "child")
	parent = _member(family, parent_id, "parent")
	if slot not in {"parent1", "parent2"}:
		raise FamilyTreeValidationError("Некорректная роль родителя.", code="bad_parent_slot")

	second_parent = child.parent2 if slot == "parent1" else child.parent1
	validate_parent_assignment(child, parent, second_parent=second_parent)
	setattr(child, slot, parent)
	child.in_tree = True
	parent.in_tree = True
	child.save(update_fields=[slot, "in_tree"])
	parent.save(update_fields=["in_tree"])
	return child


def clear_parent_slot(family, *, child_id, slot):
	member = _member(family, child_id, "child")
	if slot not in {"parent1", "parent2"}:
		raise FamilyTreeValidationError("Некорректная роль родителя.", code="bad_parent_slot")
	setattr(member, slot, None)
	member.in_tree = True
	member.save(update_fields=[slot, "in_tree"])
	return member


@transaction.atomic
def apply_relation_action(family: Family, action: str, payload: dict):
	if action == "restore_tree":
		restore_tree_snapshot(family, payload.get("snapshot"))
		return None

	if action == "create_member":
		return create_member(
			family,
			first_name=payload.get("first_name"),
			last_name=payload.get("last_name", ""),
			middle_name=payload.get("middle_name", ""),
			relation=payload.get("relation", ""),
			birth_date=payload.get("birth_date") or None,
		)

	if action == "pair":
		member_a = _member(family, payload.get("memberA"), "memberA")
		member_b = _member(family, payload.get("memberB"), "memberB")
		validate_pair(member_a, member_b)
		member_a.spouse = member_b
		member_b.spouse = member_a
		member_a.in_tree = True
		member_b.in_tree = True
		member_a.save(update_fields=["spouse", "in_tree"])
		member_b.save(update_fields=["spouse", "in_tree"])
		return member_a

	if action == "add_child":
		child = _member(family, payload.get("child"), "child")
		parent1 = _member(family, payload.get("parent1"), "parent1")
		parent2 = _member(family, payload.get("parent2"), "parent2")
		validate_parent_assignment(child, parent1, second_parent=parent2)
		child.parent1 = parent1
		child.parent2 = parent2
		child.in_tree = True
		parent1.in_tree = True
		parent2.in_tree = True
		child.save(update_fields=["parent1", "parent2", "in_tree"])
		parent1.save(update_fields=["in_tree"])
		parent2.save(update_fields=["in_tree"])
		return child

	if action == "set_mother":
		return set_parent_slot(
			family,
			child_id=payload.get("child"),
			parent_id=payload.get("parent"),
			slot="parent1",
		)

	if action == "set_father":
		return set_parent_slot(
			family,
			child_id=payload.get("child"),
			parent_id=payload.get("parent"),
			slot="parent2",
		)

	if action == "clear_mother":
		return clear_parent_slot(family, child_id=payload.get("child"), slot="parent1")

	if action == "clear_father":
		return clear_parent_slot(family, child_id=payload.get("child"), slot="parent2")

	if action == "set_parent":
		child = _member(family, payload.get("child"), "child")
		parent = _member(family, payload.get("parent"), "parent")
		current_parent_ids = [child.parent1_id, child.parent2_id]
		if parent.id in current_parent_ids:
			raise FamilyTreeValidationError("Этот родитель уже указан.", code="duplicate_parent")
		if child.parent1_id and child.parent2_id:
			raise FamilyTreeValidationError("У ребёнка уже указаны два родителя.", code="parents_full")
		second_parent = _member(family, child.parent1_id, "parent1") if child.parent1_id else None
		validate_parent_assignment(child, parent, second_parent=second_parent)
		if child.parent1_id is None:
			child.parent1 = parent
		else:
			child.parent2 = parent
		child.in_tree = True
		parent.in_tree = True
		child.save(update_fields=["parent1", "parent2", "in_tree"])
		parent.save(update_fields=["in_tree"])
		return child

	if action == "clear_parents":
		member = _member(family, payload.get("member"))
		member.parent1 = None
		member.parent2 = None
		member.in_tree = True
		member.save(update_fields=["parent1", "parent2", "in_tree"])
		return member

	if action == "remove_from_tree":
		member = _member(family, payload.get("member"))
		member.parent1 = None
		member.parent2 = None
		if member.spouse_id:
			spouse = member.spouse
			member.spouse = None
			member.save(update_fields=["parent1", "parent2", "spouse"])
			if spouse and spouse.family_id == family.id:
				spouse.spouse = None
				spouse.save(update_fields=["spouse"])
		member.in_tree = False
		member.save(update_fields=["in_tree"])
		return member

	if action == "unpair":
		member = _member(family, payload.get("member"))
		if member.spouse_id:
			spouse = member.spouse
			member.spouse = None
			member.save(update_fields=["spouse"])
			if spouse and spouse.family_id == family.id:
				spouse.spouse = None
				spouse.save(update_fields=["spouse"])
		return member

	if action == "clear_tree":
		family.family_members.update(parent1=None, parent2=None, spouse=None, in_tree=False)
		return None

	if action == "show_all":
		family.family_members.update(in_tree=True)
		return None

	raise FamilyTreeValidationError("Неизвестное действие.", code="unknown_action")


def validate_family_tree(family):
	issues = []
	seen_names = {}
	for member in family.family_members.all():
		name_key = (
			member.first_name.strip().casefold(),
			member.last_name.strip().casefold(),
			member.middle_name.strip().casefold(),
			member.birth_date,
		)
		if name_key in seen_names and any(name_key):
			issues.append(TreeIssue("duplicate_member", f"Возможный дубль: {member}.", member.id))
		seen_names[name_key] = member.id

		if member.spouse_id:
			if member.spouse_id == member.id:
				issues.append(TreeIssue("self_pair", f"{member} указан супругом самому себе.", member.id))
			elif not member.spouse or member.spouse.spouse_id != member.id:
				issues.append(TreeIssue("one_sided_spouse", f"Связь пары у {member} односторонняя.", member.id))

		parent_ids = [pid for pid in [member.parent1_id, member.parent2_id] if pid]
		if len(parent_ids) != len(set(parent_ids)):
			issues.append(TreeIssue("duplicate_parent", f"У {member} дважды указан один родитель.", member.id))
		if member.id in parent_ids:
			issues.append(TreeIssue("self_parent", f"{member} указан своим родителем.", member.id))
		for parent_id in parent_ids:
			parent = FamilyMember.objects.filter(id=parent_id, family=family).first()
			if parent and _would_create_parent_cycle(member, parent):
				issues.append(TreeIssue("parent_cycle", f"В ветке {member} найден цикл родителей.", member.id))

	return issues

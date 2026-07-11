"""Deterministic owner-scoped Gateway ``/study`` commands (M5)."""
from __future__ import annotations
import hashlib
from learning.learning_context import LearningExecutionContext
from learning.learning_store import LearningStore
from learning.semantic_review import requires_semantic_review

def _activate(ctx: LearningExecutionContext, artifact: dict) -> None:
    artifact_id, kind = artifact["artifact_id"], artifact["kind"]
    if requires_semantic_review(artifact) and artifact["review"]["status"] != "passed":
        raise ValueError("semantic review has not passed")
    if kind == "flashcard_deck":
        from learning.flashcards import FlashcardService
        FlashcardService(ctx).activate_deck(artifact_id)
    elif kind == "quiz":
        from learning.quizzes import QuizService
        QuizService(ctx).activate_quiz(artifact_id)
    elif kind == "learning_plan":
        from learning.learning_plans import LearningPlanService
        LearningPlanService(ctx).activate_plan(artifact_id)
    elif kind == "student_state":
        from learning.student_state import StudentStateService
        StudentStateService(ctx).activate_state(artifact_id)
    elif kind == "evaluation":
        from learning.evaluations import EvaluationService
        EvaluationService(ctx).activate_evaluation(artifact_id)
    else:
        ctx.set_artifact_status(artifact_id, "active")

def gateway_owner_id(platform: str, user_id: str) -> str:
    digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:16]
    return f"gateway:{platform}:{digest}"

def handle_study_command(platform: str, user_id: str, raw_args: str) -> str:
    if not platform or not user_id:
        return "Study commands require a stable sender identity."
    parts = raw_args.strip().split(maxsplit=1)
    action = parts[0].lower() if parts else "list"
    argument = parts[1].strip() if len(parts) > 1 else ""
    store = LearningStore()
    try:
        ctx = LearningExecutionContext(store, gateway_owner_id(platform, user_id))
        if action == "list":
            spaces = ctx.list_spaces()
            return "No study spaces." if not spaces else "\n".join(
                f"{'* ' if space['is_current'] else ''}{space['space_id']}: {space['title']}"
                for space in spaces
            )
        if action == "new":
            if not argument:
                return "Usage: /study new <name>"
            return f"Study space created: {ctx.create_space(title=argument)}"
        if action == "use":
            if not argument:
                return "Usage: /study use <space-id>"
            ctx.select_space(argument)
            return f"Using study space: {argument}"
        if action == "drafts":
            drafts = ctx.list_artifacts(status="draft")
            return "No study drafts." if not drafts else "\n".join(
                f"{item['artifact_id']}: {item['kind']} — {item['title']} ({item['review']['status']})"
                for item in drafts
            )
        if action in {"approve", "reject"}:
            if not argument:
                return f"Usage: /study {action} <artifact-id>"
            if action == "approve":
                artifact = ctx.get_artifact(argument)
                if not artifact:
                    return "Study draft not found."
                _activate(ctx, artifact)
                return f"Study draft approved: {argument}"
            ctx.set_artifact_status(argument, "rejected")
            return f"Study draft rejected: {argument}"
        if action == "audit":
            if not argument:
                return "Usage: /study audit <artifact-id>"
            artifact = ctx.get_artifact(argument)
            if not artifact:
                return "Study audit failed: artifact not found."
            refs = artifact["envelope"].get("source_refs") or []
            return "No external source references." if not refs else "Source references:\n" + "\n".join(str(ref) for ref in refs)
        return "Usage: /study [list|new <name>|use <space-id>|drafts|approve <artifact-id>|reject <artifact-id>|audit <artifact-id>]"
    except (KeyError, ValueError) as exc:
        return f"Study command failed: {exc}"
    finally:
        store.close()

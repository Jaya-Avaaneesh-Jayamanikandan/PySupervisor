# Re-import everything after reset
import os
import re
from pathlib import Path
import typer
from typing import List
from datetime import datetime
from typing import Optional

app = typer.Typer()

TODO_START = "''' <---TODO LIST - START--->"
TODO_END = "<---TODO LIST - END--->'''"

def find_python_files(root: Path) -> List[Path]:
    return [p for p in root.rglob("*.py") if p.is_file()]

def parse_todo_block(text: str) -> List[str] | None:
    pattern = re.compile(
        rf"{re.escape(TODO_START)}(.*?){re.escape(TODO_END)}",
        re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return None
    content = match.group(1).strip()
    return content.splitlines() if content else []

def ensure_todo_block(file_path: Path) -> bool:
    text = file_path.read_text(encoding="utf-8")
    if TODO_START in text and TODO_END in text:
        return False
    with file_path.open("a", encoding="utf-8") as f:
        f.write(f"\n{TODO_START}\n{TODO_END}\n")
    return True

def format_priority(level: int | None) -> str:
    priorities = {1: "LOW", 2: "MEDIUM", 3: "HIGH", 4: "URGENT"}
    return f"[{priorities.get(level)}]" if level in priorities else ""

def build_task_line(index: int, task: str, priority: int | None, due: str | None, assigned: str | None) -> str:
    parts = [f"({index})"]
    if priority:
        parts.append(format_priority(priority))
    parts.append(task)
    if due:
        try:
            datetime.strptime(due, "%Y-%m-%d")
            parts.append(f"Due: {due}")
        except ValueError:
            raise typer.BadParameter("Due date must be in YYYY-MM-DD format")
    if assigned:
        parts.append(f"Assigned: {assigned}")
    return " ".join(parts)

@app.command()
def scan(path: Path = typer.Option(..., help="Project root directory")):
    """Runs a scan for the TODO blocks across all Python files in the particular directory passed. If the TODO blocks are not present, they will be added automatically."""
    files = find_python_files(path)
    for file in files:
        added = ensure_todo_block(file)
        text = file.read_text(encoding="utf-8")
        todos = parse_todo_block(text)

        if added:
            typer.echo(f"[{file}] ✅ Initialized TODO block (no tasks yet)\n")
        elif todos:
            typer.echo(f"[{file}]")
            for todo in todos:
                typer.echo(f"  {todo}")
            typer.echo("")
        else:
            typer.echo(f"[{file}] 🚫 TODO block is empty\n")

@app.command()
def list(
    path: Path = typer.Option(..., help="Project root directory"),
    sort: Optional[str] = typer.Option(None, help="Sort by: ascending_id, descending_id, a-z, z-a, ascending_due_date, descending_due_date, a-z_assignedname, z-a_assignedname"),
):
    """Lists all the tasks in the TODO blocks across all Python files in the particular directory passed. You can also sort the list for easier viewing. Sorting options:
    (1) Task ID: Ascending Order -> ascending_id,
    (2) Task ID: Descending Order -> descending_id,
    (3) Task Name: A-Z Order -> a-z,
    (4) Task Name: Z-A Order -> z-a,
    (5) Due Date: Ascending Order -> ascending_due_date,
    (6) Due Date: Descending Order -> descending_due_date,
    (7) Assigned Name: A-Z Order -> a-z_assignedname,
    (8) Assigned Name: Z-A Order -> z-a_assignedname
    """
    files = find_python_files(path)
    sort_options = {
        "ascending_id", "descending_id", "a-z", "z-a",
        "ascending_due_date", "descending_due_date",
        "a-z_assignedname", "z-a_assignedname"
    }

    if sort and sort not in sort_options:
        typer.echo(f"❌ Invalid sort option. Use one of: {', '.join(sorted(sort_options))}")
        raise typer.Exit(code=1)

    def extract_due(todo: str) -> str:
        match = re.search(r"Due:\s*(\d{4}-\d{2}-\d{2})", todo)
        return match.group(1) if match else "9999-12-31"

    def extract_assigned(todo: str) -> str:
        match = re.search(r"Assigned:\s*(\w+)", todo)
        return match.group(1).lower() if match else ""

    for file in files:
        text = file.read_text(encoding="utf-8")
        todos = parse_todo_block(text)
        typer.echo(f"📄 {file}")

        if todos:
            if sort == "ascending_id":
                todos = todos
            elif sort == "descending_id":
                todos = list(reversed(todos))
            elif sort == "a-z":
                todos = sorted(todos, key=lambda x: x.lower())
            elif sort == "z-a":
                todos = sorted(todos, key=lambda x: x.lower(), reverse=True)
            elif sort == "ascending_due_date":
                todos = sorted(todos, key=extract_due)
            elif sort == "descending_due_date":
                todos = sorted(todos, key=extract_due, reverse=True)
            elif sort == "a-z_assignedname":
                todos = sorted(todos, key=extract_assigned)
            elif sort == "z-a_assignedname":
                todos = sorted(todos, key=extract_assigned, reverse=True)

            for i, todo in enumerate(todos):
                typer.echo(f"  [{i}] {todo}")
        else:
            typer.echo("  [EMPTY TODO SECTION]")
        typer.echo("")

@app.command()
def clean(path: Path = typer.Option(..., help="Project root directory")):
    """Removes all TODO blocks present in a particular directory for a production build. While leaving TODO blocks present will not impact performance, it would make the code look cleaner."""
    files = find_python_files(path)
    for file in files:
        text = file.read_text(encoding="utf-8")
        if TODO_START in text and TODO_END in text:
            new_text = re.sub(
                rf"\n?{re.escape(TODO_START)}.*?{re.escape(TODO_END)}\n?",
                "",
                text,
                flags=re.DOTALL,
            )
            file.write_text(new_text, encoding="utf-8")
            typer.echo(f"[{file}] 🧹 Removed TODO block")

@app.command()
def add(
    file: Path = typer.Option(..., help="Target Python file"),
    task: str = typer.Option(..., help="Task description"),
    priority: int = typer.Option(None, help="Priority (1=LOW to 4=URGENT)"),
    due: str = typer.Option(None, help="Due date (YYYY-MM-DD)"),
    assigned: str = typer.Option(None, help="Assignee"),
):
    """Add a TODO task to a specific file with optional metadata."""
    if not file.exists():
        typer.echo(f"❌ File not found: {file}")
        raise typer.Exit(code=1)

    added = ensure_todo_block(file)

    content = file.read_text(encoding="utf-8")
    todos = parse_todo_block(content) or []

    new_index = len(todos) + 1
    new_task_line = build_task_line(new_index, task, priority, due, assigned)
    todos.append(new_task_line)

    new_block = f"{TODO_START}\n" + "\n".join(todos) + f"\n{TODO_END}"
    if TODO_START in content and TODO_END in content:
        content = re.sub(
            rf"{re.escape(TODO_START)}.*?{re.escape(TODO_END)}",
            new_block,
            content,
            flags=re.DOTALL,
        )
    else:
        content += "\n" + new_block

    file.write_text(content, encoding="utf-8")
    typer.echo(f"✅ Task added to {file}:\n  {new_task_line}")

@app.command()
def complete(
    file: Path = typer.Option(..., help="Python file"),
    id: int = typer.Option(..., help="Task ID (0-based index)"),
):
    """Complete a task by its ID (removes it from the TODO block)"""
    if not file.exists():
        typer.echo(f"❌ File not found: {file}")
        raise typer.Exit(code=1)

    content = file.read_text(encoding="utf-8")
    todos = parse_todo_block(content)

    if not todos:
        typer.echo("⚠️ No TODOs found in file.")
        raise typer.Exit(code=1)

    if id < 0 or id >= len(todos):
        typer.echo(f"⚠️ Invalid ID. There are {len(todos)} tasks.")
        raise typer.Exit(code=1)

    removed = todos.pop(id)
    # Re-number tasks
    updated_todos = [re.sub(r"^\(\d+\)", f"({i+1})", todo) for i, todo in enumerate(todos)]
    new_block = f"{TODO_START}\n" + "\n".join(updated_todos) + f"\n{TODO_END}"

    content = re.sub(
        rf"{re.escape(TODO_START)}.*?{re.escape(TODO_END)}",
        new_block,
        content,
        flags=re.DOTALL,
    )
    file.write_text(content, encoding="utf-8")
    typer.echo(f"✅ Removed task ID {id}: {removed.strip()}")

if __name__ == "__main__":
    app()
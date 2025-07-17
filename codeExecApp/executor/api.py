from ninja import NinjaAPI
from pydantic import BaseModel
from executor.utils import run_code_sandboxed

api = NinjaAPI()  

class CodeRequest(BaseModel):
    code: str
    language: str
    stdin: str = ""  # Optional stdin field

@api.post("/run/")
def run_code(request, payload: CodeRequest):
    result = run_code_sandboxed(payload.code, payload.language, payload.stdin)
    return result

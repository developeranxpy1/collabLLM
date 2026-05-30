




# Cold Start Notice

# Preparing the GPU VM, compiling packages,
# and downloading uncensored model weights usually takes 5 minutes or more.
#  Please wait for the printed /v1 link to appear in your Colab output
#   before connecting

# Run the cells and wait for the backend link.


# then paste the link in the text box and enter






#   !!!!!!!!!!!!!!!!!  scroll down to the end and wait for the link !!!!!!!!!!!!!!!









import os, subprocess as sp, time, sys, json, random, base64 as b64, socket, re, urllib.request as ur, datetime, textwrap

# --- CONFIG ---
RUN_LLAMA, EN_CF, EN_WEB, EN_SSH, EN_KEEP = True, True, True, False, True
CTX, GPUS = 16384, 35
M_URL = "https://huggingface.co/HauhauCS/Gemma-4-E4B-Uncensored-HauhauCS-Aggressive/resolve/main/Gemma-4-E4B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf"
M_FILE = "/content/Gemma-4-E4B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf"
LLAMA_HOST = os.environ.get("LLAMA_HOST", "127.0.0.1")
PROXY_HOST = os.environ.get("PROXY_HOST", "127.0.0.1")
WEB_HOST = os.environ.get("WEB_HOST", "127.0.0.1")

def health_host(bind_host):
    return "127.0.0.1" if bind_host in {"", "0.0.0.0", "::"} else bind_host

def run(c, out=False, check=False):
    r = sp.run(c, shell=True, capture_output=not out, text=not out)
    if check and r.returncode: print(f"\x1b[1;31m❌ Cmd Failed: {c}\n{r.stderr}\x1b[0m")
    return r

def log(icon, msg, det="", c="1;32"):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    sys.stdout.write(f"  \x1b[38;5;245m[{ts}]\x1b[0m  {icon}  \x1b[{c}m{msg}\x1b[0m" + (f" \x1b[2m↳ {det}\x1b[0m\n" if det else "\n")); sys.stdout.flush()

def wait_pt(p, n, t=40, http=False, host="127.0.0.1"):
    chk_host = health_host(host)
    for _ in range(t * 2):
        try:
            with socket.create_connection((chk_host, p), timeout=0.2):
                if not http: return True
                if ur.urlopen(ur.Request(f"http://{chk_host}:{p}/", headers={"User-Agent": "hc"}), timeout=1).getcode() < 500: return True
        except: pass
        time.sleep(0.5)
    log("❌", f"{n} Timeout", c="1;31"); return False

def dl(url, dst, msg=""):
    if os.path.exists(dst): return
    if msg: log("⏳", msg, os.path.basename(dst), "1;36")
    run(f"aria2c -x 16 -s 16 -k 1M -q -d {os.path.dirname(dst)} -o {os.path.basename(dst)} {url}", out=True)

def setup_env():
    log("🧹", "Cleaning Environment & Installing Packages", c="1;36")
    run("pkill -9 -f llama_cpp; pkill -9 -f cloudflared; pkill -9 -f ttyd; pkill -9 -f tmux; pkill -9 -f tmate; pkill -9 -f px.py; pkill -9 -f uvicorn")
    
    log("📦", "Installing system dependencies via apt...", c="1;34")
    run("sudo apt-get update -qq && sudo apt-get install -qq -y aria2 tmux tmate nodejs npm")
    if not os.path.exists("/root/.ssh/id_rsa"): run("ssh-keygen -t rsa -b 4096 -N '' -f /root/.ssh/id_rsa")
    
    if EN_WEB:
        dl("https://github.com/tsl0922/ttyd/releases/download/1.7.3/ttyd.x86_64", "/usr/local/bin/ttyd")
        run("chmod +x /usr/local/bin/ttyd")
    
    run("passwd -d root; usermod -p '' root; usermod -U root")
    log("🐍", "Installing Python dependencies...", c="1;34")
    run("pip install --upgrade --no-cache-dir httpx fastapi uvicorn pydantic sse-starlette starlette", out=True)
    os.environ["PATH"] = f"/usr/local/bin:/usr/bin:/bin:{os.environ.get('PATH', '')}"

def setup_cf():
    if not EN_CF: return
    log("🌍", "Preparing Cloudflare Tunnel...", c="1;34")
    dl("https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64", "/usr/local/bin/cloudflared")
    run("chmod +x /usr/local/bin/cloudflared")

def cf_tunnel(port, proto="http", host="127.0.0.1"):
    log("⏳", f"Creating Quick Tunnel for port {port}...", c="1;33")
    log_file = f"/root/cf_{port}.log"
    if os.path.exists(log_file): os.remove(log_file)
    
    cmd = f"cloudflared tunnel --no-autoupdate --url {proto}://{health_host(host)}:{port}"
    sp.Popen(cmd, shell=True, stdout=open(log_file, "w"), stderr=sp.STDOUT)
    
    for _ in range(60):
        if os.path.exists(log_file):
            content = open(log_file).read()
            for match in re.finditer(r"(https|tcp)://[a-zA-Z0-9-]+\.trycloudflare\.com", content):
                url = match.group(0)
                if "api.trycloudflare.com" not in url:
                    log("✅", f"Tunnel Online ({port})", url, "1;32")
                    return url
        time.sleep(1)
    
    log("❌", f"Cloudflare Tunnel ({port}) Timeout", c="1;31")
    return None

def init_ai():
    log("🧠", "INITIALIZING AI ENGINE", c="1;35")
    
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY")
    if api_key:
        log("⚡", "Gemini API Key detected. Using Gemini Cloud Multimodal engine.", c="1;32")
    else:
        dl(M_URL, M_FILE, "Accelerated Model Download")
        
        if not run("python3 -c 'import llama_cpp'").returncode == 0:
            log("⚙️", "Installing Llama-cpp (CUDA)...", c="1;34")
            run("pip install --upgrade --no-cache-dir 'llama-cpp-python[server]' --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124", out=True)
        
        os.environ["LLAMA_MODEL_PATH"] = M_FILE
        os.environ["LLAMA_CTX"] = str(CTX)
        os.environ["LLAMA_GPUS"] = str(GPUS)
        
    os.environ["COLLAB_PROXY_HOST"] = PROXY_HOST
    
    proxy_src = textwrap.dedent(r'''
        import asyncio
        import html
        import json
        import os
        import re
        import subprocess
        import uuid
        import time
        from urllib.parse import parse_qs, quote_plus, unquote, urlparse

        import httpx
        import uvicorn
        from fastapi import FastAPI, HTTPException, Request
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse, FileResponse

        UPSTREAM_HOST = os.environ.get("COLLAB_UPSTREAM_HOST", "127.0.0.1")
        UPSTREAM_URL = f"http://{UPSTREAM_HOST}:18081"
        DEFAULT_MODEL = "local-model"
        TOOL_TIMEOUT = 120
        MAX_TOOL_ROUNDS = 8
        MAX_OUTPUT_CHARS = 100000
        MAX_COMMAND_CHARS = 12000
        SEARCH_TIMEOUT = 30
        MAX_SEARCH_RESULTS = 4
        MAX_FETCH_CHARS = 16000
        MAX_SNIPPET_CHARS = 400
        TOOL_CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.S)
        JSON_BLOCK_RE = re.compile(r"```(?:json|tool|tool_call)?\s*(\{.*?\})\s*```", re.S)
        COMPACT_TOOL_CALL_PREFIX = "<|tool_call|>"

        IDENTITY_PROMPT = (
            "You are collabLLM, an uncensored AI assistant. "
            "If the user asks who or what you are, identify yourself as an uncensored AI assistant. "
            "Provide thorough, detailed, and accurate answers."
        )

        TOOLS_PROMPT = (
            "You also have access to terminal, search, and page-reading tools. "
            "Use tools only when they are genuinely necessary to answer correctly or complete a requested action. "
            "Do not use tools for greetings, introductions, poems, stories, creative writing, brainstorming, roleplay, or other tasks you can answer directly from the conversation. "
            "Use execute_terminal whenever you need to inspect files, install packages, run commands, or verify work. "
            "Use search_web only for current facts, external research, or when the user explicitly asks you to look something up, and use fetch_url only when reading a specific page is necessary. "
            "Do not ask the user to run commands for you when the tool can do it. "
            "After tool results arrive, continue the task and explain what you found. "
            "If native tool calling is unavailable, emit exactly one <tool_call>{...}</tool_call> block using JSON with "
            "\"name\" set to execute_terminal, search_web, or fetch_url and an \"arguments\" object for that tool."
        )

        NO_TOOLS_PROMPT = (
            "Respond naturally and do not emit tool_call blocks, XML tool tags, function-calling JSON, or tool names like execute_terminal, search_web, or fetch_url unless tools are explicitly available."
        )

        SEARCH_MODE_PROMPTS = {
            "quick": (
                "Current mode: Quick. Prefer a fast response with minimal tool usage. "
                "Search only when it materially improves correctness or when the user explicitly asks you to look something up."
            ),
            "adaptive": (
                "Current mode: Adaptive. Behave more agentically: break hard tasks into steps, research before concluding, "
                "and use search_web and fetch_url proactively when external information would help."
            ),
        }

        TOOL_NAME_ALIASES = {
            "search": "search_web",
            "fetch": "fetch_url",
            "read_url": "fetch_url",
            "web_search": "search_web",
            "code": "execute_code",
            "call_tool_chain": "execute_code",
            "codemode": "execute_code",
        }

        EXECUTE_TOOL = {
            "type": "function",
            "function": {
                "name": "execute_terminal",
                "description": "Run a shell command in the local Linux environment and return stdout, stderr, and exit status.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Shell command to execute."
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Optional timeout in seconds. Defaults to 90 and is capped at 300.",
                            "minimum": 1,
                            "maximum": 300
                        }
                    },
                    "required": ["command"]
                }
            }
        }

        SEARCH_TOOL = {
            "type": "function",
            "function": {
                "name": "search_web",
                "description": "Search the public web for sources, results, and current information.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query."
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of sources to return. Defaults to 5 and is capped at 8.",
                            "minimum": 1,
                            "maximum": 8
                        },
                        "include_domains": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional domains to prioritize or restrict to."
                        },
                        "exclude_domains": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional domains to exclude."
                        }
                    },
                    "required": ["query"]
                }
            }
        }

        FETCH_TOOL = {
            "type": "function",
            "function": {
                "name": "fetch_url",
                "description": "Fetch and extract readable text from a specific URL.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "HTTP or HTTPS URL to retrieve."
                        }
                    },
                    "required": ["url"]
                }
            }
        }

        PYTHON_TOOL = {
            "type": "function",
            "function": {
                "name": "execute_python_code",
                "description": (
                    "Runs a short Python snippet in a sandboxed environment and returns whatever it prints to stdout. "
                    "Use this for precise math, calculations, data sorting, or Python logic. The snippet must call print() to output results."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "The Python snippet to execute. Math and statistics modules are pre-imported."
                        }
                    },
                    "required": ["code"]
                }
            }
        }

        DIR_LIST_TOOL = {
            "type": "function",
            "function": {
                "name": "list_directory_contents",
                "description": "Lists all files and subdirectories inside a specific folder relative to the workspace root.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "The relative directory path to list, e.g. '.', 'data', etc. Defaults to the workspace root."
                        }
                    },
                    "required": []
                }
            }
        }

        EXECUTE_CODE_TOOL = {
            "type": "function",
            "function": {
                "name": "execute_code",
                "description": (
                    "Execute Python code in a sandboxed environment with access to tool interfaces. "
                    "Use this for code-mode / UTCP-style multi-step tool chains. "
                    "The environment exposes 'tools' as a dict of async callable interfaces for: "
                    "execute_terminal, search_web, fetch_url, execute_python_code, list_directory_contents. "
                    "Call them like: result = await tools['execute_terminal']({'command': 'ls'}). "
                    "The sandbox has async/await support and returns stdout + stderr. "
                    "Always use print() to output results you want returned."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "Python code to execute. Supports async/await. Use tools['tool_name'] to call tools."
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Execution timeout in seconds (default 60, max 300).",
                            "minimum": 1,
                            "maximum": 300
                        }
                    },
                    "required": ["code"]
                }
            }
        }

        SUPPORTED_TOOLS = {
            "execute_terminal": EXECUTE_TOOL,
            "search_web": SEARCH_TOOL,
            "fetch_url": FETCH_TOOL,
            "execute_python_code": PYTHON_TOOL,
            "list_directory_contents": DIR_LIST_TOOL,
            "execute_code": EXECUTE_CODE_TOOL,
        }
        SUPPORTED_TOOL_NAMES = tuple(SUPPORTED_TOOLS.keys())

        app = FastAPI()
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        client = httpx.AsyncClient(
            base_url=UPSTREAM_URL,
            timeout=httpx.Timeout(None, connect=60.0),
        )

        # Conditionally load local model or skip if using Gemini Cloud Multimodal engine
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY")
        if not api_key:
            from llama_cpp import Llama
            MODEL_PATH = os.environ.get("LLAMA_MODEL_PATH", "/content/Gemma-4-E4B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf")
            CTX = int(os.environ.get("LLAMA_CTX", "16384"))
            GPUS = int(os.environ.get("LLAMA_GPUS", "35"))
            
            llm = Llama(
                model_path=MODEL_PATH,
                n_ctx=CTX,
                n_gpu_layers=GPUS,
                verbose=False
            )
        else:
            llm = None

        async def run_in_thread(func, *args, **kwargs):
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

        async def iterate_in_thread(sync_generator):
            def get_next():
                try:
                    return next(sync_generator), False
                except StopIteration:
                    return None, True
            while True:
                item, done = await run_in_thread(get_next)
                if done:
                    break
                yield item

        def filter_llm_kwargs(payload):
            allowed_keys = {
                "messages", "tools", "tool_choice", "stream", "temperature",
                "top_p", "top_k", "min_p", "typical_p", "presence_penalty",
                "frequency_penalty", "repeat_penalty", "max_tokens", "stop",
                "seed", "response_format", "model"
            }
            return {k: v for k, v in payload.items() if k in allowed_keys}


        def clean_headers(headers):
            return {
                k: v for k, v in headers.items()
                if k.lower() not in {
                    "host", "content-length", "connection", "keep-alive",
                    "proxy-connection", "transfer-encoding"
                }
            }

        def clip_text(value, limit=MAX_OUTPUT_CHARS):
            text = value or ""
            if len(text) <= limit:
                return text
            clipped = len(text) - limit
            return text[:limit] + f"\n...[truncated {clipped} chars]"

        def stringify_content(content):
            if isinstance(content, str):
                return content
            if content is None:
                return ""
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        parts.append(item.get("text", ""))
                    else:
                        parts.append(json.dumps(item, ensure_ascii=False))
                return "\n".join(part for part in parts if part)
            return json.dumps(content, ensure_ascii=False)

        import io
        import contextlib
        import math
        import statistics

        def execute_python_code(code: str) -> str:
            try:
                safe_builtins = {
                    "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
                    "divmod": divmod, "enumerate": enumerate, "filter": filter, "float": float,
                    "int": int, "len": len, "list": list, "map": map, "max": max, "min": min,
                    "pow": pow, "print": print, "range": range, "repr": repr, "reversed": reversed,
                    "round": round, "set": set, "sorted": sorted, "str": str, "sum": sum,
                    "tuple": tuple, "zip": zip,
                }
                restricted_globals = {
                    "__builtins__": safe_builtins,
                    "math": math,
                    "statistics": statistics,
                }

                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    exec(code, restricted_globals, {})

                output = buffer.getvalue().strip()
                if not output:
                    return "Code executed successfully but produced no output. Use print() to return a value."
                return f"Output:\n{output}"
            except Exception as e:
                return f"Execution error: {type(e).__name__}: {e}"

        def list_directory_contents(path: str = ".") -> str:
            try:
                safe_base = os.path.abspath(os.getcwd())
                requested = os.path.abspath(os.path.join(safe_base, path or "."))
                if not (requested == safe_base or requested.startswith(safe_base + os.sep)):
                    return f"Error: Access denied. Path '{path}' is outside permitted workspace."

                if not os.path.exists(requested):
                    return f"Error: Path '{path}' does not exist."

                if not os.path.isdir(requested):
                    return f"Error: Path '{path}' is not a directory."

                entries = sorted(os.listdir(requested))
                if not entries:
                    return f"The directory '{path}' is empty."

                lines = [f"Contents of '{path}' ({len(entries)} item(s)):"]
                for name in entries:
                    full = os.path.join(requested, name)
                    if os.path.isdir(full):
                        lines.append(f"  [DIR]  {name}/")
                    else:
                        try:
                            size = os.path.getsize(full)
                            lines.append(f"  [FILE] {name} ({size} bytes)")
                        except OSError:
                            lines.append(f"  [FILE] {name}")
                return "\n".join(lines)
            except Exception as e:
                return f"Error listing directory '{path}': {e}"

        async def run_execute_code(code, timeout=60):
            code = str(code or "").strip()
            if not code:
                return {"ok": False, "exit_code": -1, "stdout": "", "stderr": "Missing code.", "output": "Missing code.", "timed_out": False}
            loop = asyncio.get_running_loop()
            def _run():
                try:
                    import io, contextlib, json, asyncio
                    safe_builtins = {
                        "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
                        "divmod": divmod, "enumerate": enumerate, "filter": filter, "float": float,
                        "int": int, "len": len, "list": list, "map": map, "max": max, "min": min,
                        "pow": pow, "print": print, "range": range, "repr": repr, "reversed": reversed,
                        "round": round, "set": set, "sorted": sorted, "str": str, "sum": sum,
                        "tuple": tuple, "zip": zip, "isinstance": isinstance, "type": type,
                        "True": True, "False": False, "None": None, "object": object,
                        "Exception": Exception, "ValueError": ValueError, "TypeError": TypeError,
                        "KeyError": KeyError, "IndexError": IndexError, "AttributeError": AttributeError,
                        "RuntimeError": RuntimeError, "StopIteration": StopIteration,
                        "hasattr": hasattr, "getattr": getattr, "setattr": setattr, "delattr": delattr,
                        "len": len, "range": range, "enumerate": enumerate, "zip": zip,
                        "map": map, "filter": filter, "iter": iter, "next": next,
                        "reversed": reversed, "sorted": sorted, "min": min, "max": max,
                        "sum": sum, "any": any, "all": all, "dict": dict, "list": list,
                        "set": set, "tuple": tuple, "str": str, "int": int, "float": float,
                        "bool": bool, "bytes": bytes, "bytearray": bytearray,
                        "chr": chr, "ord": ord, "hex": hex, "oct": oct, "bin": bin,
                        "format": format, "id": id, "hash": hash,
                    }
                    restricted = {
                        "__builtins__": safe_builtins,
                        "math": __import__("math"),
                        "statistics": __import__("statistics"),
                        "json": json,
                        "datetime": __import__("datetime"),
                        "time": __import__("time"),
                        "re": __import__("re"),
                        "collections": __import__("collections"),
                        "itertools": __import__("itertools"),
                        "functools": __import__("functools"),
                        "uuid": __import__("uuid"),
                        "typing": __import__("typing"),
                    }
                    buffer = io.StringIO()
                    async def call_tool(name, args_dict):
                        import subprocess, urllib.request, json
                        if name == "execute_terminal":
                            cmd = str(args_dict.get("command", ""))
                            t_out = max(1, min(int(args_dict.get("timeout", 90)), 300))
                            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=t_out)
                            out = proc.stdout.strip()
                            err = proc.stderr.strip()
                            combined = "\n".join(p for p in [out, err] if p) or "(No output)"
                            return {"ok": proc.returncode == 0, "exit_code": proc.returncode, "stdout": out, "stderr": err, "output": combined}
                        elif name == "search_web":
                            q = str(args_dict.get("query", ""))
                            try:
                                with urllib.request.urlopen(f"https://api.duckduckgo.com/?q={urllib.request.quote(q)}&format=json&no_html=1", timeout=15) as resp:
                                    data = json.loads(resp.read())
                                results = []
                                for topic in data.get("RelatedTopics", [])[:5]:
                                    if "Text" in topic and "FirstURL" in topic:
                                        results.append({"title": topic.get("Text", "").split(" - ")[0], "url": topic["FirstURL"], "snippet": topic.get("Text", "")})
                                return {"ok": True, "output": json.dumps(results, indent=2)}
                            except Exception as e:
                                return {"ok": False, "output": f"Search error: {e}"}
                        elif name == "fetch_url":
                            url = str(args_dict.get("url", ""))
                            try:
                                with urllib.request.urlopen(url, timeout=15) as resp:
                                    content = resp.read().decode("utf-8", errors="replace")
                                import re
                                text = re.sub(r"(?is)<script[^>]*>.*?</script>", "", content)
                                text = re.sub(r"(?is)<style[^>]*>.*?</style>", "", text)
                                text = re.sub(r"(?i)<br\s*/?>", "\n", text)
                                text = re.sub(r"(?is)<[^>]+>", "", text)
                                text = "\n".join(line for line in text.split("\n") if line.strip())
                                return {"ok": True, "output": text[:5000]}
                            except Exception as e:
                                return {"ok": False, "output": f"Fetch error: {e}"}
                        elif name == "execute_python_code":
                            return {"ok": True, "output": execute_python_code(args_dict.get("code", ""))}
                        elif name == "list_directory_contents":
                            return {"ok": True, "output": list_directory_contents(args_dict.get("path", "."))}
                        return {"ok": False, "output": f"Unknown tool: {name}"}
                    restricted["tools"] = {
                        "execute_terminal": lambda **kw: asyncio.run(call_tool("execute_terminal", kw)),
                        "search_web": lambda **kw: asyncio.run(call_tool("search_web", kw)),
                        "fetch_url": lambda **kw: asyncio.run(call_tool("fetch_url", kw)),
                        "execute_python_code": lambda **kw: call_tool("execute_python_code", kw),
                        "list_directory_contents": lambda **kw: call_tool("list_directory_contents", kw),
                    }
                    with contextlib.redirect_stdout(buffer):
                        restricted["__result__"] = None
                        exec(f"async def __cm_exec():\n" + "\n".join("  " + ln for ln in code.split("\n")), restricted)
                        restricted["__result__"] = asyncio.run(restricted["__cm_exec"]())
                    stdout = buffer.getvalue().strip()
                    output = stdout or (json.dumps(restricted.get("__result__")) if restricted.get("__result__") is not None else "")
                    return {"ok": True, "exit_code": 0, "stdout": stdout, "stderr": "", "output": output or "(No output)", "timed_out": False}
                except subprocess.TimeoutExpired:
                    return {"ok": False, "exit_code": -1, "stdout": "", "stderr": f"Execution timed out after {timeout}s.", "output": f"Execution timed out after {timeout}s.", "timed_out": True}
                except Exception as e:
                    err_msg = f"{type(e).__name__}: {e}"
                    return {"ok": False, "exit_code": 1, "stdout": "", "stderr": err_msg, "output": err_msg, "timed_out": False}
            try:
                return await loop.run_in_executor(None, _run)
            except Exception as e:
                return {"ok": False, "exit_code": 1, "stdout": "", "stderr": str(e), "output": str(e), "timed_out": False}

        def get_gemini_config(payload):
            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY")
            model = payload.get("model", "")
            if model == DEFAULT_MODEL or not model or model == "local-model":
                model = "gemini-2.5-flash"
            return api_key, model

        def openai_to_gemini_contents(messages):
            gemini_contents = []
            system_instruction = None
            
            for msg in messages:
                role = msg.get("role")
                content = msg.get("content")
                
                if role == "system":
                    system_instruction = {"parts": [{"text": stringify_content(content)}]}
                    continue
                
                g_role = "model" if role == "assistant" else "user"
                
                parts = []
                if isinstance(content, str):
                    parts.append({"text": content})
                elif isinstance(content, list):
                    for part in content:
                        if not isinstance(part, dict):
                            continue
                        p_type = part.get("type")
                        if p_type == "text":
                            parts.append({"text": part.get("text", "")})
                        elif p_type == "image_url":
                            url = part.get("image_url", {}).get("url", "")
                            if url.startswith("data:"):
                                try:
                                    header, base64_data = url.split(";base64,", 1)
                                    mime_type = header.split("data:", 1)[1]
                                    parts.append({
                                        "inlineData": {
                                            "mimeType": mime_type,
                                            "data": base64_data
                                        }
                                    })
                                except Exception:
                                    pass
                
                if parts:
                    gemini_contents.append({
                        "role": g_role,
                        "parts": parts
                    })
                    
            return gemini_contents, system_instruction

        def gemini_to_openai_response(gemini_resp, model):
            candidates = gemini_resp.get("candidates", [])
            text = ""
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                text = "".join(part.get("text", "") for part in parts)
                
            return {
                "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": text
                        },
                        "finish_reason": "stop"
                    }
                ]
            }

        async def run_gemini_nonstream(payload):
            api_key, model = get_gemini_config(payload)
            if not api_key:
                raise HTTPException(status_code=400, detail="Gemini API Key is not set.")
            
            messages = list(payload["messages"])
            contents, system_instruction = openai_to_gemini_contents(messages)
            
            generation_config = {}
            if "temperature" in payload:
                generation_config["temperature"] = payload["temperature"]
            if "top_p" in payload:
                generation_config["topP"] = payload["top_p"]
            if "max_tokens" in payload:
                generation_config["maxOutputTokens"] = payload["max_tokens"]
                
            body = {
                "contents": contents,
                "generationConfig": generation_config
            }
            if system_instruction:
                body["systemInstruction"] = system_instruction
                
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            
            async with httpx.AsyncClient(timeout=httpx.Timeout(None, connect=30.0)) as http_client:
                response = await http_client.post(url, json=body)
                response.raise_for_status()
                gemini_resp = response.json()
                return gemini_to_openai_response(gemini_resp, model)

        async def stream_gemini_direct(payload):
            api_key, model = get_gemini_config(payload)
            if not api_key:
                raise HTTPException(status_code=400, detail="Gemini API Key is not set.")
            
            messages = list(payload["messages"])
            contents, system_instruction = openai_to_gemini_contents(messages)
            
            generation_config = {}
            if "temperature" in payload:
                generation_config["temperature"] = payload["temperature"]
            if "top_p" in payload:
                generation_config["topP"] = payload["top_p"]
            if "max_tokens" in payload:
                generation_config["maxOutputTokens"] = payload["max_tokens"]
                
            body = {
                "contents": contents,
                "generationConfig": generation_config
            }
            if system_instruction:
                body["systemInstruction"] = system_instruction
                
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?key={api_key}&alt=sse"
            
            async with httpx.AsyncClient(timeout=httpx.Timeout(None, connect=30.0)) as http_client:
                async with http_client.stream("POST", url, json=body) as response:
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line.startswith("data:"):
                            continue
                        try:
                            data = json.loads(line[5:].strip())
                            candidates = data.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                text = "".join(part.get("text", "") for part in parts)
                                if text:
                                    yield text
                        except Exception:
                            pass

        async def stream_chat_gemini_without_tools(raw_payload):
            api_key, model = get_gemini_config(raw_payload)
            yield sse_delta("")
            try:
                async for chunk_text in stream_gemini_direct(raw_payload):
                    if chunk_text:
                        yield sse_delta(chunk_text)
            except Exception as e:
                yield sse_delta(f"\n[Gemini Stream Error: {e}]")
            yield sse_done()

        def extract_text_content(content, separator=""):
            if isinstance(content, str):
                return content
            if content is None:
                return ""
            if isinstance(content, list):
                parts = [
                    extract_text_content(item, separator=separator)
                    for item in content
                ]
                return separator.join(part for part in parts if part)
            if isinstance(content, dict):
                text_value = content.get("text")
                if isinstance(text_value, str):
                    return text_value
                if isinstance(text_value, dict):
                    nested_value = text_value.get("value")
                    if isinstance(nested_value, str):
                        return nested_value
                inner_content = content.get("content")
                if isinstance(inner_content, str):
                    return inner_content
                if isinstance(inner_content, list):
                    return extract_text_content(inner_content, separator=separator)
                for key in ("value", "delta"):
                    value = content.get(key)
                    if isinstance(value, str):
                        return value
                return ""
            return str(content)

        def extract_last_user_text(messages):
            for message in reversed(list(messages or [])):
                if message.get("role") == "user":

                    return stringify_content(message.get("content"))
            return ""

        def normalize_search_mode(value):
            value = str(value or "").strip().lower()
            return value if value in SEARCH_MODE_PROMPTS else "quick"

        def extract_search_mode(payload):
            payload = payload or {}
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
            return normalize_search_mode(
                payload.get("search_mode")
                or payload.get("searchMode")
                or metadata.get("search_mode")
                or metadata.get("searchMode")
            )

        def is_social_prompt(text):
            lowered = str(text or "").strip().lower()
            if not lowered:
                return False
            simple_patterns = (
                r"^(hi|hello|hey|yo|sup)\b",
                r"\bintroduce yourself\b",
                r"\bintro\b",
                r"\bwho are you\b",
                r"\bwhat are you\b",
                r"\bwhat can you do\b",
                r"\btell me about yourself\b",
            )
            return any(re.search(pattern, lowered) for pattern in simple_patterns) and len(lowered) <= 160

        def is_creative_prompt(text):
            lowered = str(text or "").strip().lower()
            if not lowered:
                return False
            creative_patterns = [
                r"\bpoem\b",
                r"\bpoetry\b",
                r"\bstory\b",
                r"\bnovel\b",
                r"\bessay\b",
                r"\bjoke\b",
                r"\blyrics?\b",
                r"\bbrainstorm\b",
                r"\bcreative\b",
                r"\bfiction\b",
                r"\broleplay\b",
                r"\bscript\b",
            ]
            return any(re.search(pattern, lowered) for pattern in creative_patterns)

        def looks_like_tool_request(text):
            lowered = str(text or "").lower()
            tool_patterns = [
                r"\b(run|execute|install|apt|pip|npm|yarn|pnpm|cargo|brew)\b",
                r"\b(search|look up|lookup|find online|web search|google|duckduckgo|browse)\b",
                r"\b(fetch|read url|open url|visit|check website|scrape)\b",
                r"\b(file|files|folder|directory|repo|repository|codebase|debug|fix|patch|error|traceback|log)\b",
                r"\b(latest|current|today|news|price|release|docs?)\b",
                r"`{3}",
                r"\b(shell|bash|powershell|terminal|command line)\b",
            ]
            return any(re.search(pattern, lowered) for pattern in tool_patterns)

        def should_enable_tools(messages, search_mode="quick"):
            latest_user = extract_last_user_text(messages)
            if is_social_prompt(latest_user):
                return False
            if is_creative_prompt(latest_user) and not looks_like_tool_request(latest_user):
                return False
            return looks_like_tool_request(latest_user)

        def dedupe_tool_names(names):
            seen = set()
            ordered = []
            for name in names or []:
                normalized = normalize_tool_name(name)
                if normalized in SUPPORTED_TOOL_NAMES and normalized not in seen:
                    seen.add(normalized)
                    ordered.append(normalized)
            return ordered

        def coerce_bool(value):
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in {"1", "true", "yes", "on"}:
                    return True
                if lowered in {"0", "false", "no", "off"}:
                    return False
            return None

        def extract_supported_tool_names(tools):
            names = []
            for tool in tools or []:
                if not isinstance(tool, dict):
                    continue
                function = tool.get("function") if isinstance(tool.get("function"), dict) else {}
                name = normalize_tool_name(function.get("name") or tool.get("name"))
                if name in SUPPORTED_TOOL_NAMES:
                    names.append(name)
            return dedupe_tool_names(names)

        def normalize_requested_tool_choice(tool_choice):
            if tool_choice in (None, ""):
                return None
            if isinstance(tool_choice, str):
                normalized = normalize_tool_name(tool_choice)
                if normalized in SUPPORTED_TOOL_NAMES:
                    return normalized
                if normalized in {"auto", "required", "none"}:
                    return normalized
                return None
            if isinstance(tool_choice, dict):
                if tool_choice.get("type") != "function":
                    return None
                function = tool_choice.get("function") if isinstance(tool_choice.get("function"), dict) else {}
                name = normalize_tool_name(function.get("name"))
                if name in SUPPORTED_TOOL_NAMES:
                    return {"type": "function", "function": {"name": name}}
            return None

        def resolve_tool_policy(raw_payload, search_mode="quick"):
            payload = dict(raw_payload or {})
            metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
            requested_tool_names = extract_supported_tool_names(payload.get("tools") or [])
            requested_tool_choice = normalize_requested_tool_choice(payload.get("tool_choice"))
            explicit_disable = (
                requested_tool_choice == "none"
                or coerce_bool(payload.get("disable_tools")) is True
                or coerce_bool(metadata.get("disable_tools")) is True
            )
            explicit_enable = (
                bool(requested_tool_names)
                or isinstance(requested_tool_choice, dict)
                or (isinstance(requested_tool_choice, str) and requested_tool_choice in SUPPORTED_TOOL_NAMES)
                or coerce_bool(payload.get("enable_tools")) is True
                or coerce_bool(metadata.get("enable_tools")) is True
            )

            if explicit_disable:
                tools_enabled = False
            elif explicit_enable:
                tools_enabled = True
            else:
                tools_enabled = should_enable_tools(payload.get("messages") or [], search_mode)

            available_tool_names = []
            if tools_enabled:
                available_tool_names = list(requested_tool_names or infer_relevant_tool_names(payload.get("messages") or []))
                if isinstance(requested_tool_choice, dict):
                    chosen_name = normalize_tool_name((requested_tool_choice.get("function") or {}).get("name"))
                    available_tool_names = dedupe_tool_names([*available_tool_names, chosen_name])
                elif isinstance(requested_tool_choice, str) and requested_tool_choice in SUPPORTED_TOOL_NAMES:
                    available_tool_names = dedupe_tool_names([*available_tool_names, requested_tool_choice])
                else:
                    available_tool_names = dedupe_tool_names(available_tool_names)

            return {
                "tools_enabled": tools_enabled,
                "available_tool_names": available_tool_names,
                "requested_tool_choice": requested_tool_choice,
            }

        def infer_relevant_tool_names(messages):
            latest_user = str(extract_last_user_text(messages) or "").lower()
            inferred = []
            if re.search(r"\b(search|look up|lookup|find online|web search|google|duckduckgo|browse|latest|current|today|news|price|release|docs?)\b", latest_user):
                inferred.extend(["search_web", "fetch_url"])
            if re.search(r"\b(fetch|read url|open url|visit|check website|scrape|page|article|link|url)\b", latest_user):
                inferred.append("fetch_url")
            if re.search(r"\b(run|execute|install|apt|pip|npm|yarn|pnpm|cargo|brew|file|files|folder|directory|repo|repository|codebase|debug|fix|patch|error|traceback|log|shell|bash|powershell|terminal|command line)\b", latest_user):
                inferred.append("execute_terminal")
            if re.search(r"\b(python|eval|exec|calc|calculate|math|statistics|solve)\b", latest_user):
                inferred.append("execute_python_code")
            if re.search(r"\b(list files|ls|dir|files|folder contents)\b", latest_user):
                inferred.append("list_directory_contents")
            if re.search(r"\b(code|script|automate|multi.tep|chain|pipeline|workflow|batch|codemode)\b", latest_user):
                inferred.append("execute_code")
            return dedupe_tool_names(inferred or SUPPORTED_TOOL_NAMES)

        def build_tools_prompt(available_tool_names):
            tool_names = dedupe_tool_names(available_tool_names or SUPPORTED_TOOL_NAMES)
            if not tool_names:
                return ""
            tool_lines = []
            if "execute_terminal" in tool_names:
                tool_lines.append(
                    "Use execute_terminal whenever you need to inspect files, install packages, run commands, or verify work."
                )
            if "search_web" in tool_names:
                tool_lines.append(
                    "Use search_web only for current facts, external research, or when the user explicitly asks you to look something up."
                )
            if "fetch_url" in tool_names:
                tool_lines.append(
                    "Use fetch_url only when reading a specific page is necessary."
                )
            if "execute_python_code" in tool_names:
                tool_lines.append(
                    "Use execute_python_code to run safe Python snippets for precise math, calculations, or string logic."
                )
            if "list_directory_contents" in tool_names:
                tool_lines.append(
                    "Use list_directory_contents to securely list the folders and files in the permitted workspace."
                )
            if "execute_code" in tool_names:
                tool_lines.append(
                    "Use execute_code to write and run Python that chains multiple tool calls together in a single execution. "
                    "The sandbox exposes tools as async callables via tools['tool_name']({'arg': 'value'}). "
                    "Prefer execute_code over individual tool calls when you need to chain, loop, or conditionally branch between tools."
                )
            fallback_names = ", ".join(f'"{name}"' for name in tool_names)
            return (
                "You also have access to tools. "
                "Use tools only when they are genuinely necessary to answer correctly or complete a requested action. "
                "Do not use tools for greetings, introductions, poems, stories, creative writing, brainstorming, roleplay, or other tasks you can answer directly from the conversation. "
                f"Tools available for this response: {', '.join(tool_names)}. "
                + " ".join(tool_lines)
                + " Do not ask the user to run commands for you when the tool can do it. "
                + "After tool results arrive, continue the task and explain what you found. "
                + "If native tool calling is unavailable, emit exactly one <tool_call>{...}</tool_call> block using JSON with "
                + f"\"name\" set to one of {fallback_names} and an \"arguments\" object for that tool."
            )

        def build_system_prompt(search_mode="quick", tools_enabled=True, available_tool_names=None):
            sections = [IDENTITY_PROMPT]
            if tools_enabled:
                sections.append(build_tools_prompt(available_tool_names))
            else:
                sections.append(NO_TOOLS_PROMPT)
            sections.append(
                SEARCH_MODE_PROMPTS.get(normalize_search_mode(search_mode), SEARCH_MODE_PROMPTS["quick"])
            )
            return "\n\n".join(section for section in sections if section)

        def ensure_system_message(messages, search_mode="quick", tools_enabled=True, available_tool_names=None):
            normalized = list(messages or [])
            system_prompt = build_system_prompt(
                search_mode=search_mode,
                tools_enabled=tools_enabled,
                available_tool_names=available_tool_names,
            )
            tools_prompt = build_tools_prompt(available_tool_names) if tools_enabled else ""
            for idx, message in enumerate(normalized):
                if message.get("role") == "system":
                    content = stringify_content(message.get("content"))
                    if IDENTITY_PROMPT not in content:
                        content = f"{content}\n\n{system_prompt}" if content else system_prompt
                    elif tools_enabled and tools_prompt and tools_prompt not in content:
                        content = f"{content}\n\n{tools_prompt}"
                    elif not tools_enabled and NO_TOOLS_PROMPT not in content:
                        content = f"{content}\n\n{NO_TOOLS_PROMPT}"
                    mode_prompt = SEARCH_MODE_PROMPTS.get(
                        normalize_search_mode(search_mode),
                        SEARCH_MODE_PROMPTS["quick"],
                    )
                    if mode_prompt not in content:
                        content = f"{content}\n\n{mode_prompt}"
                    normalized[idx] = {**message, "content": content}
                    return normalized
            return [{"role": "system", "content": system_prompt}, *normalized]

        def ensure_tools(payload, tools_enabled=True, available_tool_names=None, requested_tool_choice=None):
            if not tools_enabled:
                payload.pop("tools", None)
                payload.pop("tool_choice", None)
                return payload
            resolved_tool_names = dedupe_tool_names(available_tool_names or SUPPORTED_TOOL_NAMES)
            payload["tools"] = [SUPPORTED_TOOLS[name] for name in resolved_tool_names]
            normalized_tool_choice = normalize_requested_tool_choice(
                requested_tool_choice if requested_tool_choice is not None else payload.get("tool_choice")
            )
            if normalized_tool_choice == "none":
                payload.pop("tools", None)
                payload.pop("tool_choice", None)
                return payload
            if isinstance(normalized_tool_choice, dict):
                requested_name = normalize_tool_name((normalized_tool_choice.get("function") or {}).get("name"))
                payload["tool_choice"] = (
                    normalized_tool_choice
                    if requested_name in resolved_tool_names
                    else "auto"
                )
                return payload
            if normalized_tool_choice in {"auto", "required"}:
                payload["tool_choice"] = normalized_tool_choice
                return payload
            if normalized_tool_choice in resolved_tool_names:
                payload["tool_choice"] = {
                    "type": "function",
                    "function": {"name": normalized_tool_choice},
                }
                return payload
            payload["tool_choice"] = "auto"
            return payload

        def build_chat_payload(raw_payload):
            payload = dict(raw_payload or {})
            search_mode = extract_search_mode(payload)
            tool_policy = resolve_tool_policy(payload, search_mode=search_mode)
            tools_enabled = tool_policy["tools_enabled"]
            available_tool_names = tool_policy["available_tool_names"]
            requested_tool_choice = tool_policy["requested_tool_choice"]
            payload["model"] = payload.get("model") or DEFAULT_MODEL
            payload["messages"] = ensure_system_message(
                payload.get("messages") or [],
                search_mode=search_mode,
                tools_enabled=tools_enabled,
                available_tool_names=available_tool_names,
            )
            payload["search_mode"] = search_mode
            payload["tools_enabled"] = tools_enabled
            payload["available_tool_names"] = list(available_tool_names)
            payload["requested_tool_choice"] = requested_tool_choice
            payload["stream"] = False
            return ensure_tools(
                payload,
                tools_enabled=tools_enabled,
                available_tool_names=available_tool_names,
                requested_tool_choice=requested_tool_choice,
            )

        def to_upstream_payload(payload, history):
            upstream_payload = {
                key: value
                for key, value in dict(payload or {}).items()
                if key not in {
                    "search_mode",
                    "searchMode",
                    "metadata",
                    "tools_enabled",
                    "available_tool_names",
                    "requested_tool_choice",
                    "enable_tools",
                    "disable_tools",
                }
            }
            upstream_payload["messages"] = history
            # Force high token limit to prevent truncation from the frontend
            upstream_payload["max_tokens"] = max(upstream_payload.get("max_tokens", 0), 4096)
            # Remove n_predict — it is not a valid OpenAI API parameter and gets ignored
            upstream_payload.pop("n_predict", None)
            return upstream_payload

        def normalize_assistant_message(message):
            msg = dict(message or {})
            normalized = {
                "role": msg.get("role") or "assistant",
                "content": stringify_content(msg.get("content"))
            }
            if msg.get("tool_calls"):
                normalized["tool_calls"] = msg["tool_calls"]
            return normalized

        def json_dumps_compact(value):
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

        def normalize_tool_name(name):
            normalized = str(name or "").strip()
            return TOOL_NAME_ALIASES.get(normalized, normalized)

        def normalize_tool_markup_text(value):
            return (
                str(value or "")
                .replace('<|"|>', '"')
                .replace("<|'|>", "'")
                .replace("<|n|>", "\n")
            )

        def contains_manual_tool_syntax(text):
            text = str(text or "")
            return "<tool_call" in text or COMPACT_TOOL_CALL_PREFIX in text

        def extract_stream_text(choice):
            choice = choice or {}
            delta = choice.get("delta") if isinstance(choice.get("delta"), dict) else {}
            message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
            candidate = delta.get("content")
            if candidate in (None, ""):
                candidate = message.get("content")
            if candidate in (None, ""):
                candidate = choice.get("text") or ""
            return extract_text_content(candidate, separator="")

        def merge_stream_text(current_text, next_text):
            if not next_text:
                return current_text, ""
            if not current_text:
                return next_text, next_text
            if next_text == current_text:
                return current_text, ""
            if next_text.startswith(current_text):
                appended = next_text[len(current_text):]
                return next_text, appended
            return current_text + next_text, next_text

        def clip_snippet(value, limit=MAX_SNIPPET_CHARS):
            text = re.sub(r"\s+", " ", str(value or "")).strip()
            if len(text) <= limit:
                return text
            return text[:limit].rstrip() + "..."

        def extract_domain(url):
            try:
                return urlparse(url).netloc.lower()
            except Exception:
                return ""

        def decode_search_result_url(href):
            href = html.unescape(str(href or ""))
            if href.startswith("//"):
                href = "https:" + href
            if href.startswith("/"):
                href = "https://duckduckgo.com" + href
            try:
                parsed = urlparse(href)
                if parsed.netloc.endswith("duckduckgo.com"):
                    target = parse_qs(parsed.query).get("uddg", [None])[0]
                    if target:
                        return unquote(target)
            except Exception:
                pass
            return href

        def strip_html_text(value):
            text = str(value or "")
            text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", text)
            text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
            text = re.sub(r"(?is)<noscript[^>]*>.*?</noscript>", " ", text)
            text = re.sub(r"(?i)<br\s*/?>", "\n", text)
            text = re.sub(r"(?i)</p\s*>", "\n\n", text)
            text = re.sub(r"(?i)</div\s*>", "\n", text)
            text = re.sub(r"(?s)<[^>]+>", " ", text)
            text = html.unescape(text)
            text = re.sub(r"[ \t\r\f\v]+", " ", text)
            text = re.sub(r"\n{3,}", "\n\n", text)
            return text.strip()

        def build_search_query(query, include_domains=None, exclude_domains=None):
            terms = [str(query or "").strip()]
            for domain in include_domains or []:
                domain = str(domain or "").strip()
                if domain:
                    terms.append(f"site:{domain}")
            for domain in exclude_domains or []:
                domain = str(domain or "").strip()
                if domain:
                    terms.append(f"-site:{domain}")
            return " ".join(term for term in terms if term).strip()

        def summarize_search_results(query, results):
            if not results:
                return f'No search results found for "{query}".'
            lines = [f'Search results for "{query}":']
            for idx, item in enumerate(results, start=1):
                title = item.get("title") or item.get("url") or f"Result {idx}"
                url = item.get("url") or ""
                snippet = clip_snippet(item.get("snippet") or "")
                lines.append(f"{idx}. {title}")
                if url:
                    lines.append(f"   URL: {url}")
                if snippet:
                    lines.append(f"   Snippet: {snippet}")
            return "\n".join(lines)

        def parse_loose_tool_arguments(raw_text):
            text = normalize_tool_markup_text(raw_text).strip()
            if not text:
                return {}
            candidate = text if text.startswith("{") and text.endswith("}") else "{" + text + "}"
            candidate = re.sub(r'([{,]\s*)([A-Za-z_][A-Za-z0-9_\-]*)\s*:', r'\1"\2":', candidate)
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                args = {}
                parts = re.split(r',(?=(?:[^"]*"[^"]*")*[^"]*$)', text)
                for part in parts:
                    if ":" not in part:
                        continue
                    key, value = part.split(":", 1)
                    key = key.strip().strip('"\'')
                    value = normalize_tool_markup_text(value).strip()
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    args[key] = value
                return args

        def coerce_tool_call(raw):
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except json.JSONDecodeError:
                    return None
            if not isinstance(raw, dict):
                return None

            function = raw.get("function") if isinstance(raw.get("function"), dict) else {}
            name = normalize_tool_name(raw.get("name") or function.get("name") or raw.get("tool"))
            arguments = raw.get("arguments")
            if arguments is None:
                arguments = raw.get("args") or raw.get("input") or raw.get("parameters")
            if arguments is None:
                arguments = function.get("arguments")
            if arguments is None and raw.get("command"):
                arguments = {"command": raw.get("command")}
            if arguments is None and raw.get("query"):
                arguments = {"query": raw.get("query")}
            if arguments is None and raw.get("url"):
                arguments = {"url": raw.get("url")}
            if not name:
                return None

            if isinstance(arguments, str):
                try:
                    parsed_args = json.loads(arguments)
                    arguments = parsed_args
                except json.JSONDecodeError:
                    arguments = {"command": arguments}
            elif arguments is None:
                arguments = {}

            if isinstance(arguments, dict):
                command = (
                    arguments.get("command")
                    or arguments.get("cmd")
                    or arguments.get("shell")
                    or arguments.get("shell_command")
                    or arguments.get("bash")
                )
                if command is not None:
                    arguments["command"] = command
                if name == "search_web" and arguments.get("query") is None:
                    query = arguments.get("q") or arguments.get("search") or arguments.get("term")
                    if query is not None:
                        arguments["query"] = query
                if name == "fetch_url" and arguments.get("url") is None:
                    url = arguments.get("href") or arguments.get("link")
                    if url is not None:
                        arguments["url"] = url

            return {
                "id": raw.get("id") or f"call_{uuid.uuid4().hex[:12]}",
                "type": raw.get("type") or "function",
                "function": {
                    "name": name,
                    "arguments": json_dumps_compact(arguments),
                },
            }

        def iter_tagged_tool_json(content):
            decoder = json.JSONDecoder()
            pos = 0
            while True:
                start = content.find("<tool_call", pos)
                if start == -1:
                    break
                tag_end = content.find(">", start)
                if tag_end == -1:
                    break
                body_start = tag_end + 1
                end_tag = content.find("</tool_call>", body_start)
                raw_body = content[body_start:end_tag if end_tag != -1 else len(content)]
                stripped = raw_body.lstrip()
                leading_ws = len(raw_body) - len(stripped)
                try:
                    raw, used = decoder.raw_decode(stripped)
                except json.JSONDecodeError:
                    pos = body_start
                    continue
                json_end = body_start + leading_ws + used
                span_end = end_tag + len("</tool_call>") if end_tag != -1 else json_end
                yield raw, start, span_end
                pos = span_end

        def find_matching_brace(text, start_index):
            depth = 0
            quote_char = None
            escape = False
            for idx in range(start_index, len(text)):
                ch = text[idx]
                if quote_char:
                    if escape:
                        escape = False
                    elif ch == "\\":
                        escape = True
                    elif ch == quote_char:
                        quote_char = None
                    continue
                if ch in ('"', "'"):
                    quote_char = ch
                    continue
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        return idx
            return -1

        def iter_compact_tool_calls(content):
            pos = 0
            while True:
                start = content.find(COMPACT_TOOL_CALL_PREFIX, pos)
                if start == -1:
                    break
                cursor = start + len(COMPACT_TOOL_CALL_PREFIX)
                match = re.match(r"\s*call:([A-Za-z0-9_\-:]+)\s*\{", content[cursor:])
                if not match:
                    pos = cursor
                    continue
                name = match.group(1)
                brace_start = cursor + match.end() - 1
                brace_end = find_matching_brace(content, brace_start)
                if brace_end == -1:
                    break
                body = content[brace_start + 1:brace_end]
                yield {
                    "name": name,
                    "arguments": parse_loose_tool_arguments(body),
                }, start, brace_end + 1
                pos = brace_end + 1

        def iter_markdown_tool_json(content):
            for match in JSON_BLOCK_RE.finditer(content):
                block = match.group(1)
                if (
                    "execute_terminal" not in block
                    and "search_web" not in block
                    and "fetch_url" not in block
                    and '"command"' not in block
                    and '"cmd"' not in block
                    and '"query"' not in block
                    and '"url"' not in block
                ):
                    continue
                try:
                    yield json.loads(block), match.start(), match.end()
                except json.JSONDecodeError:
                    continue

        def parse_manual_tool_calls(content):
            if not content:
                return [], content
            tool_calls = []
            spans = []
            raw_matches = (
                list(iter_tagged_tool_json(content))
                + list(iter_markdown_tool_json(content))
                + list(iter_compact_tool_calls(content))
            )
            for raw, start, end in raw_matches:
                tool_call = coerce_tool_call(raw)
                if tool_call:
                    tool_calls.append(tool_call)
                    spans.append((start, end))
            if not tool_calls:
                return [], content
            cleaned_parts = []
            last = 0
            for start, end in sorted(spans):
                cleaned_parts.append(content[last:start])
                last = end
            cleaned_parts.append(content[last:])
            cleaned = "".join(cleaned_parts).strip()
            return tool_calls, cleaned if tool_calls else content

        def extract_tool_calls(message):
            normalized = normalize_assistant_message(message)
            native_calls = normalized.get("tool_calls") or []
            if native_calls:
                return native_calls, normalized
            manual_calls, cleaned = parse_manual_tool_calls(normalized.get("content", ""))
            normalized["content"] = cleaned
            return manual_calls, normalized

        def strip_manual_tool_syntax(content):
            _, cleaned = parse_manual_tool_calls(str(content or ""))
            return cleaned.strip()

        async def run_terminal_command(command, timeout):
            command = str(command or "").strip()
            if not command:
                return {
                    "ok": False,
                    "command": command,
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": "Missing command.",
                    "output": "Missing command.",
                    "timed_out": False,
                }
            if "\x00" in command:
                return {
                    "ok": False,
                    "command": command,
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": "Command contains a NUL byte.",
                    "output": "Command contains a NUL byte.",
                    "timed_out": False,
                }
            if len(command) > MAX_COMMAND_CHARS:
                return {
                    "ok": False,
                    "command": command[:MAX_COMMAND_CHARS],
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": f"Command is too long. Limit is {MAX_COMMAND_CHARS} characters.",
                    "output": f"Command is too long. Limit is {MAX_COMMAND_CHARS} characters.",
                    "timed_out": False,
                }
            timeout = max(1, min(int(timeout or TOOL_TIMEOUT), 300))
            loop = asyncio.get_running_loop()

            def _run():
                try:
                    proc = subprocess.run(
                        command,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                    )
                    stdout = clip_text(proc.stdout)
                    stderr = clip_text(proc.stderr)
                    combined = "\n".join(part for part in [stdout, stderr] if part).strip()
                    return {
                        "ok": proc.returncode == 0,
                        "command": command,
                        "exit_code": proc.returncode,
                        "stdout": stdout,
                        "stderr": stderr,
                        "output": combined or "(No output)",
                        "timed_out": False,
                    }
                except subprocess.TimeoutExpired as exc:
                    stdout = clip_text(exc.stdout if isinstance(exc.stdout, str) else "")
                    stderr = clip_text(exc.stderr if isinstance(exc.stderr, str) else "")
                    stderr = (stderr + "\n" if stderr else "") + f"Command timed out after {timeout}s."
                    combined = "\n".join(part for part in [stdout, stderr] if part).strip()
                    return {
                        "ok": False,
                        "command": command,
                        "exit_code": -1,
                        "stdout": stdout,
                        "stderr": stderr,
                        "output": combined or stderr,
                        "timed_out": True,
                    }
                except Exception as exc:
                    err = str(exc)
                    return {
                        "ok": False,
                        "command": command,
                        "exit_code": -1,
                        "stdout": "",
                        "stderr": err,
                        "output": err,
                        "timed_out": False,
                    }

            return await loop.run_in_executor(None, _run)

        async def run_web_search(query, max_results, include_domains=None, exclude_domains=None):
            query = str(query or "").strip()
            include_domains = [str(item).strip() for item in (include_domains or []) if str(item).strip()]
            exclude_domains = [str(item).strip() for item in (exclude_domains or []) if str(item).strip()]
            if not query:
                return {
                    "ok": False,
                    "query": query,
                    "results": [],
                    "stderr": "Missing query.",
                    "output": "Missing query.",
                }

            effective_max_results = max(1, min(int(max_results or 5), MAX_SEARCH_RESULTS))
            search_query = build_search_query(query, include_domains, exclude_domains)
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; collabLLM/1.0; +https://example.invalid)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
            urls = [
                f"https://html.duckduckgo.com/html/?q={quote_plus(search_query)}",
                f"https://duckduckgo.com/html/?q={quote_plus(search_query)}",
            ]
            last_error = None
            html_text = ""

            async with httpx.AsyncClient(follow_redirects=True, timeout=SEARCH_TIMEOUT, headers=headers) as external_client:
                for candidate in urls:
                    try:
                        response = await external_client.get(candidate)
                        response.raise_for_status()
                        html_text = response.text
                        if html_text:
                            break
                    except Exception as exc:
                        last_error = exc

            if not html_text:
                err = str(last_error or "Search request failed.")
                return {
                    "ok": False,
                    "query": query,
                    "results": [],
                    "stderr": err,
                    "output": err,
                }

            anchor_pattern = re.compile(
                r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
                re.I | re.S,
            )
            snippet_pattern = re.compile(r'class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</', re.I | re.S)
            results = []
            seen_urls = set()

            for match in anchor_pattern.finditer(html_text):
                url = decode_search_result_url(match.group(1))
                if not url.startswith("http://") and not url.startswith("https://"):
                    continue
                domain = extract_domain(url)
                if include_domains and not any(domain.endswith(item.lower()) for item in include_domains):
                    continue
                if exclude_domains and any(domain.endswith(item.lower()) for item in exclude_domains):
                    continue
                if url in seen_urls:
                    continue

                title = clip_snippet(strip_html_text(match.group(2)), 180)
                nearby = html_text[match.end():match.end() + 1400]
                snippet_match = snippet_pattern.search(nearby)
                snippet = clip_snippet(strip_html_text(snippet_match.group(1)) if snippet_match else "", MAX_SNIPPET_CHARS)
                if not title:
                    continue

                seen_urls.add(url)
                results.append({
                    "title": title,
                    "url": url,
                    "domain": domain,
                    "snippet": snippet,
                })
                if len(results) >= effective_max_results:
                    break

            if not results:
                try:
                    async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT, headers={"User-Agent": headers["User-Agent"]}) as external_client:
                        response = await external_client.get(
                            "https://api.duckduckgo.com/",
                            params={
                                "q": search_query,
                                "format": "json",
                                "no_html": "1",
                                "skip_disambig": "1",
                            },
                        )
                        response.raise_for_status()
                        data = response.json()
                    abstract = clip_snippet(data.get("AbstractText") or "", MAX_SNIPPET_CHARS)
                    abstract_url = data.get("AbstractURL") or ""
                    heading = data.get("Heading") or query
                    if abstract:
                        results.append({
                            "title": heading,
                            "url": abstract_url,
                            "domain": extract_domain(abstract_url),
                            "snippet": abstract,
                        })
                except Exception as exc:
                    last_error = exc

            return {
                "ok": True,
                "provider": "duckduckgo",
                "query": query,
                "search_query": search_query,
                "include_domains": include_domains,
                "exclude_domains": exclude_domains,
                "results": results,
                "output": summarize_search_results(query, results),
                "stderr": "" if results else str(last_error or ""),
            }

        async def fetch_url_content(url):
            url = str(url or "").strip()
            if not re.match(r"^https?://", url, re.I):
                return {
                    "ok": False,
                    "url": url,
                    "stderr": "URL must start with http:// or https://.",
                    "output": "URL must start with http:// or https://.",
                }

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; collabLLM/1.0; +https://example.invalid)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
            }

            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=SEARCH_TIMEOUT, headers=headers) as external_client:
                    response = await external_client.get(url)
                    response.raise_for_status()
            except Exception as exc:
                err = str(exc)
                return {
                    "ok": False,
                    "url": url,
                    "stderr": err,
                    "output": err,
                }

            content_type = response.headers.get("content-type", "")
            raw_text = response.text
            title_match = re.search(r"<title[^>]*>(.*?)</title>", raw_text, re.I | re.S)
            title = clip_snippet(strip_html_text(title_match.group(1)) if title_match else extract_domain(str(response.url)) or url, 160)

            if "text/html" in content_type or "application/xhtml+xml" in content_type:
                content = strip_html_text(raw_text)
            elif content_type.startswith("text/") or "json" in content_type or "xml" in content_type:
                content = raw_text.strip()
            else:
                return {
                    "ok": False,
                    "url": str(response.url),
                    "title": title,
                    "content_type": content_type,
                    "stderr": f"Unsupported content type: {content_type}",
                    "output": f"Unsupported content type: {content_type}",
                }

            clipped_content = clip_text(content, MAX_FETCH_CHARS)
            return {
                "ok": True,
                "url": str(response.url),
                "title": title,
                "content_type": content_type,
                "content": clipped_content,
                "output": f"{title}\nURL: {response.url}\n\n{clipped_content}",
                "stderr": "",
            }

        async def execute_tool_call(tool_call):
            call_id = tool_call.get("id") or f"call_{uuid.uuid4().hex[:12]}"
            function = tool_call.get("function") or {}
            name = normalize_tool_name(function.get("name") or tool_call.get("name") or "")
            raw_args = function.get("arguments") or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
            except json.JSONDecodeError as exc:
                return call_id, {
                    "ok": False,
                    "tool_name": name,
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": f"Invalid tool arguments: {exc}",
                    "output": f"Invalid tool arguments: {exc}",
                    "timed_out": False,
                }
            if isinstance(args, str):
                args = {"command": args}
            if isinstance(args, dict):
                command = (
                    args.get("command")
                    or args.get("cmd")
                    or args.get("shell")
                    or args.get("shell_command")
                    or args.get("bash")
                )
                if command is not None:
                    args["command"] = command
                if name == "search_web" and args.get("query") is None:
                    query = args.get("q") or args.get("search") or args.get("term")
                    if query is not None:
                        args["query"] = query
                if name == "fetch_url" and args.get("url") is None:
                    url = args.get("href") or args.get("link")
                    if url is not None:
                        args["url"] = url
            if name == "execute_terminal":
                timeout = args.get("timeout", TOOL_TIMEOUT)
                result = await run_terminal_command(args.get("command", ""), timeout)
            elif name == "search_web":
                result = await run_web_search(
                    args.get("query", ""),
                    args.get("max_results", 5),
                    args.get("include_domains") or [],
                    args.get("exclude_domains") or [],
                )
            elif name == "fetch_url":
                result = await fetch_url_content(args.get("url", ""))
            elif name == "execute_python_code":
                result = {
                    "ok": True,
                    "output": execute_python_code(args.get("code", "")),
                    "stderr": ""
                }
            elif name == "list_directory_contents":
                result = {
                    "ok": True,
                    "output": list_directory_contents(args.get("path", ".")),
                    "stderr": ""
                }
            elif name == "execute_code":
                code = args.get("code", "")
                timeout_val = max(1, min(int(args.get("timeout", 60)), 300))
                result = await run_execute_code(code, timeout_val)
            else:
                return call_id, {
                    "ok": False,
                    "tool_name": name,
                    "exit_code": -1,
                    "stdout": "",
                    "stderr": f"Unsupported tool: {name}",
                    "output": f"Unsupported tool: {name}",
                    "timed_out": False,
                }
            result["tool_name"] = name
            return call_id, result

        async def run_chat_without_tools(raw_payload):
            payload = build_chat_payload(raw_payload)
            upstream_payload = to_upstream_payload(payload, list(payload["messages"]))
            api_key, model = get_gemini_config(payload)
            if api_key:
                data = await run_gemini_nonstream(upstream_payload)
            else:
                kwargs = filter_llm_kwargs(upstream_payload)
                data = await run_in_thread(llm.create_chat_completion, **kwargs)
            choices = data.get("choices") or []
            if not choices:
                return data
            choice = choices[0]
            assistant_source = choice.get("message") or {
                "role": "assistant",
                "content": choice.get("text") or "",
            }
            message = normalize_assistant_message(assistant_source)
            if contains_manual_tool_syntax(message.get("content", "")):
                message["content"] = strip_manual_tool_syntax(message.get("content", ""))
            data["choices"][0]["message"] = message
            data["choices"][0]["finish_reason"] = choice.get("finish_reason") or "stop"
            return data


        def get_continuation_messages(original_messages, full_text):
            last_word = full_text.split()[-1] if (full_text and full_text.strip()) else ""
            instruction = (
                f"Your previous response was cut off midway. Please continue generating from exactly where you left off, "
                f"without repeating anything. The partial text you already wrote is:\n\n{full_text}\n\n"
                f"Continue the sentence immediately starting with the next word after '{last_word}'!"
            )
            return list(original_messages) + [
                {"role": "assistant", "content": full_text},
                {"role": "user", "content": instruction}
            ]

        async def stream_chat_without_tools(raw_payload):
            api_key, model = get_gemini_config(raw_payload)
            if api_key:
                async for chunk in stream_chat_gemini_without_tools(raw_payload):
                    yield chunk
                return

            payload = build_chat_payload(raw_payload)
            original_messages = list(payload["messages"])
            messages = list(original_messages)
            tool_round_limit = 3  # limit continuation rounds to avoid infinite loops
            
            yield sse_delta("")  # Open stream instantly
            
            full_text = ""
            for round_idx in range(tool_round_limit):
                upstream_payload = to_upstream_payload(payload, messages)
                upstream_payload["stream"] = True
                kwargs = filter_llm_kwargs(upstream_payload)
                
                stream_finished = False
                try:
                    sync_generator = await run_in_thread(llm.create_chat_completion, **kwargs)
                    async for chunk in iterate_in_thread(sync_generator):
                        choice = (chunk.get("choices") or [{}])[0]
                        delta = choice.get("delta") or {}
                        content = extract_text_content(delta.get("content") or "", separator="")
                        
                        if content:
                            full_text += content
                            yield sse_delta(content)
                            
                        finish_reason = choice.get("finish_reason")
                        if finish_reason in {"stop", "length"}:
                            stream_finished = True
                    stream_finished = True
                except Exception as exc:
                    pass
                
                # If the stream finished gracefully (we got stop finish_reason or [DONE])
                # and the text doesn't look cut off (e.g. ends with a space or punctuation or typical ending)
                if stream_finished and (not full_text or full_text[-1] in {".", "!", "?", '"', "'", "\n", " ", ")", "}"}):
                    break
                    
                # Otherwise, if it got cut off mid-word or mid-sentence, continue!
                if full_text.strip():
                    messages = get_continuation_messages(original_messages, full_text)
                    await asyncio.sleep(0.5)
                else:
                    break
                    
            yield sse_done()


        async def run_chat_with_tools(raw_payload):
            payload = build_chat_payload(raw_payload)
            history = list(payload["messages"])
            for _ in range(get_tool_round_limit(payload)):
                upstream_payload = to_upstream_payload(payload, history)
                api_key, model = get_gemini_config(payload)
                if api_key:
                    data = await run_gemini_nonstream(upstream_payload)
                else:
                    kwargs = filter_llm_kwargs(upstream_payload)
                    data = await run_in_thread(llm.create_chat_completion, **kwargs)
                choices = data.get("choices") or []
                if not choices:
                    raise HTTPException(status_code=502, detail="Upstream returned no choices.")

                choice = choices[0]
                assistant_source = choice.get("message") or {
                    "role": "assistant",
                    "content": choice.get("text") or "",
                }
                tool_calls, assistant_message = extract_tool_calls(assistant_source)
                history.append(assistant_message)

                if not tool_calls:
                    data["choices"][0]["message"] = assistant_message
                    data["choices"][0]["finish_reason"] = choice.get("finish_reason") or "stop"
                    return data

                for tool_call in tool_calls:
                    call_id, result = await execute_tool_call(tool_call)
                    history.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })

            raise HTTPException(
                status_code=500,
                detail=f"Tool execution loop exceeded {get_tool_round_limit(payload)} rounds."
            )


        async def stream_text_response(text):
            text = text or ""
            chunk_size = 160
            for start in range(0, len(text), chunk_size):
                chunk = text[start:start + chunk_size]
                payload = {
                    "choices": [{
                        "index": 0,
                        "delta": {"content": chunk},
                        "finish_reason": None,
                    }]
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")
            final_payload = {
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop",
                }]
            }
            yield f"data: {json.dumps(final_payload, ensure_ascii=False)}\n\n".encode("utf-8")
            yield b"data: [DONE]\n\n"

        def sse_delta(content):
            payload = {
                "choices": [{
                    "index": 0,
                    "delta": {"content": content},
                    "finish_reason": None,
                }],
                "completed": False
            }
            return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")

        def sse_done():
            final_payload = {
                "choices": [{
                    "index": 0,
                    "delta": {"content": ""},
                    "finish_reason": "stop",
                }],
                "completed": True
            }
            return (
                f"data: {json.dumps(final_payload, ensure_ascii=False)}\n\n"
                "data: [DONE]\n\n"
            ).encode("utf-8")

        def sse_keepalive(note="keepalive"):
            return f": {note}\n\n".encode("utf-8")

        def merge_tool_call_delta(tool_calls_by_index, delta_tool_calls):
            for item in delta_tool_calls or []:
                idx = item.get("index", 0)
                current = tool_calls_by_index.setdefault(idx, {
                    "id": item.get("id") or f"call_{uuid.uuid4().hex[:12]}",
                    "type": item.get("type") or "function",
                    "function": {"name": "", "arguments": ""},
                })
                if item.get("id"):
                    current["id"] = item["id"]
                if item.get("type"):
                    current["type"] = item["type"]
                fn = item.get("function") or {}
                if fn.get("name"):
                    current["function"]["name"] += fn["name"]
                if fn.get("arguments"):
                    current["function"]["arguments"] += fn["arguments"]

        def get_tool_round_limit(payload):
            search_mode = normalize_search_mode((payload or {}).get("search_mode"))
            return MAX_TOOL_ROUNDS + 2 if search_mode == "adaptive" else MAX_TOOL_ROUNDS

        def describe_tool_status(tool_name, args, phase="start", result=None):
            tool_name = normalize_tool_name(tool_name)
            args = args or {}
            if tool_name == "search_web":
                query = str(args.get("query") or "").strip() or "the web"
                if phase == "start":
                    return f'> Searching the web for "{query}"...'
                count = len((result or {}).get("results") or [])
                return f"> Search complete: found {count} source{'s' if count != 1 else ''} for \"{query}\"."
            if tool_name == "fetch_url":
                url = str(args.get("url") or "").strip() or "the page"
                if phase == "start":
                    return f"> Reading {url}..."
                title = (result or {}).get("title") or extract_domain(url) or url
                return f"> Finished reading: {title}."
            if tool_name == "execute_terminal":
                command = str(args.get("command") or "").strip()
                display = command if len(command) <= 80 else command[:77] + "..."
                if phase == "start":
                    return f"> Running terminal command: `{display}`"
                if result and result.get("ok"):
                    return f"> Command completed successfully: `{display}`"
                return f"> Command finished with an error: `{display}`"
            if tool_name == "execute_python_code":
                if phase == "start":
                    return f"> Executing Python code block..."
                return f"> Python execution complete."
            if tool_name == "list_directory_contents":
                path = args.get("path") or "."
                if phase == "start":
                    return f"> Listing contents of directory '{path}'..."
                return f"> Directory listing complete for '{path}'."
            return None

        async def stream_chat_with_tools(raw_payload):
            payload = build_chat_payload(raw_payload)
            history = list(payload["messages"])
            tool_round_limit = get_tool_round_limit(payload)
            yield sse_delta("")  # Open stream instantly

            for round_idx in range(tool_round_limit):
                upstream_payload = to_upstream_payload(payload, history)
                upstream_payload["stream"] = True

                assistant_message = {"role": "assistant", "content": ""}
                tool_calls_by_index = {}
                
                # Check if Gemini is enabled
                api_key, model = get_gemini_config(payload)
                if api_key:
                    try:
                        async for chunk_text in stream_gemini_direct(upstream_payload):
                            if chunk_text:
                                assistant_message["content"] += chunk_text
                                yield sse_delta(chunk_text)
                    except Exception as e:
                        yield sse_delta(f"\n[Gemini Tool Stream Error: {e}]")
                    stream_finished = True
                else:
                    continuation_rounds = 3
                    for cont_idx in range(continuation_rounds):
                        if cont_idx > 0:
                            # Continue using the smart instruction
                            temp_history = get_continuation_messages(history, assistant_message["content"])
                            upstream_payload = to_upstream_payload(payload, temp_history)
                        
                        kwargs = filter_llm_kwargs(upstream_payload)
                        stream_finished = False
                        try:
                            sync_generator = await run_in_thread(llm.create_chat_completion, **kwargs)
                            async for chunk in iterate_in_thread(sync_generator):
                                choice = (chunk.get("choices") or [{}])[0]
                                delta = choice.get("delta") or {}
                                content = extract_text_content(delta.get("content") or "", separator="")
                                if content:
                                    assistant_message["content"] += content
                                    yield sse_delta(content)

                                merge_tool_call_delta(tool_calls_by_index, delta.get("tool_calls"))
                                
                                finish_reason = choice.get("finish_reason")
                                if finish_reason in {"stop", "length", "tool_calls"}:
                                    stream_finished = True
                            stream_finished = True
                        except Exception as exc:
                            pass
                            
                        # If stream finished and is not cut off mid-word, stop continuing
                        full_text = assistant_message["content"]
                        if stream_finished and (not full_text or full_text[-1] in {".", "!", "?", '"', "'", "\n", " ", ")", "}"} or tool_calls_by_index):
                            break
                            
                        await asyncio.sleep(0.5)

                native_tool_calls = [
                    tool_calls_by_index[idx]
                    for idx in sorted(tool_calls_by_index)
                    if (tool_calls_by_index[idx].get("function") or {}).get("name")
                ]
                if native_tool_calls:
                    assistant_message["tool_calls"] = native_tool_calls

                tool_calls, normalized_message = extract_tool_calls(assistant_message)
                history.append(normalized_message)

                if not tool_calls:
                    yield sse_done()
                    return

                # Hide the raw fallback tag from the UI, but keep the connection warm while tools run.
                yield sse_keepalive(f"tool-round-{round_idx + 1}")

                for tool_call in tool_calls:
                    function = tool_call.get("function") or {}
                    tool_name = normalize_tool_name(function.get("name") or tool_call.get("name") or "")
                    tool_task = asyncio.create_task(execute_tool_call(tool_call))
                    while not tool_task.done():
                        yield sse_keepalive(f"tool-running-{tool_name or 'unknown'}")
                        await asyncio.sleep(2)
                    call_id, result = await tool_task
                    history.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })
                    yield sse_keepalive(f"tool-complete-{call_id}")

            error_text = f"Tool execution loop exceeded {tool_round_limit} rounds."
            yield sse_delta(error_text)
            yield sse_done()


        @app.get("/v1/models")
        async def list_models():
            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY")
            if api_key:
                return JSONResponse({
                    "object": "list",
                    "data": [
                        {"id": "gemini-2.5-flash", "object": "model", "created": 1710000000, "owned_by": "google"},
                        {"id": "gemini-2.5-pro", "object": "model", "created": 1710000000, "owned_by": "google"},
                        {"id": "gemini-1.5-flash", "object": "model", "created": 1710000000, "owned_by": "google"},
                        {"id": "gemini-1.5-pro", "object": "model", "created": 1710000000, "owned_by": "google"},
                    ]
                })
            else:
                return JSONResponse({
                    "object": "list",
                    "data": [
                        {
                            "id": DEFAULT_MODEL,
                            "object": "model",
                            "created": 1686935002,
                            "owned_by": "collabllm"
                        }
                    ]
                })

        @app.get("/v1/health")
        async def health():
            body = {
                "status": "running",
                "engine_ready": True,
                "model": DEFAULT_MODEL,
                "tools_enabled": True,
                "identity": "collabLLM",
                "available_tools": list(SUPPORTED_TOOL_NAMES),
                "tool_calling_available": True,
                "tool_availability_mode": "request-aware",
                "tool_selection_policy": "heuristic unless explicitly requested",
                "search_modes": ["quick", "adaptive"],
            }
            return JSONResponse(body)

        @app.get("/")
        async def serve_index():
            paths = ["index.html", "../index.html", "backendstuff/index.html", "/content/index.html"]
            for p in paths:
                if os.path.exists(p):
                    with open(p, "r", encoding="utf-8") as f:
                        return HTMLResponse(content=f.read())
            # Fallback
            body = {
                "status": "running",
                "engine_ready": True,
                "model": DEFAULT_MODEL,
                "tools_enabled": True,
                "identity": "collabLLM",
                "available_tools": list(SUPPORTED_TOOL_NAMES),
                "tool_calling_available": True,
                "tool_availability_mode": "request-aware",
                "tool_selection_policy": "heuristic unless explicitly requested",
                "search_modes": ["quick", "adaptive"],
            }
            return JSONResponse(body)

        @app.get("/logo.png")
        async def serve_logo():
            paths = ["logo.png", "../logo.png", "backendstuff/logo.png", "/content/logo.png"]
            for p in paths:
                if os.path.exists(p):
                    return FileResponse(p)
            raise HTTPException(status_code=404, detail="Logo not found")

        @app.get("/logo_round.png")
        async def serve_logo_round():
            paths = ["logo_round.png", "../logo_round.png", "backendstuff/logo_round.png", "/content/logo_round.png"]
            for p in paths:
                if os.path.exists(p):
                    return FileResponse(p)
            raise HTTPException(status_code=404, detail="Logo not found")


        @app.post("/v1/execute")
        async def execute_cmd(req: Request):
            try:
                data = await req.json()
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"Invalid JSON body: {exc}") from exc
            _, result = await execute_tool_call({
                "id": f"call_{uuid.uuid4().hex[:12]}",
                "function": {
                    "name": "execute_terminal",
                    "arguments": json.dumps({
                        "command": data.get("command", ""),
                        "timeout": data.get("timeout", TOOL_TIMEOUT),
                    })
                }
            })
            return JSONResponse(result)

        @app.post("/v1/chat/completions")
        async def chat_completions(req: Request):
            try:
                payload = await req.json()
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"Invalid JSON body: {exc}") from exc
            prepared = build_chat_payload(payload)
            if payload.get("stream"):
                if not prepared.get("tools_enabled", True):
                    return StreamingResponse(
                        stream_chat_without_tools(payload),
                        media_type="text/event-stream",
                        headers={
                            "cache-control": "no-cache",
                            "x-accel-buffering": "no",
                        },
                    )
                return StreamingResponse(
                    stream_chat_with_tools(payload),
                    media_type="text/event-stream",
                    headers={
                        "cache-control": "no-cache",
                        "x-accel-buffering": "no",
                    },
                )
            if not prepared.get("tools_enabled", True):
                result = await run_chat_without_tools(payload)
            else:
                result = await run_chat_with_tools(payload)
            return JSONResponse(result)

        @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
        async def px(path: str, req: Request):
            body = await req.body()
            response = await client.send(
                client.build_request(
                    req.method,
                    f"/{path}",
                    content=body if body else None,
                    headers=clean_headers(req.headers),
                ),
                stream=True,
            )

            async def stream_gen():
                try:
                    async for chunk in response.aiter_bytes():
                        yield chunk
                finally:
                    await response.aclose()

            return StreamingResponse(
                stream_gen(),
                status_code=response.status_code,
                headers={
                    **{
                        k: v for k, v in response.headers.items()
                        if k.lower() not in {
                            "transfer-encoding", "content-length", "connection",
                            "keep-alive", "proxy-connection"
                        }
                    },
                    "cache-control": "no-cache",
                    "x-accel-buffering": "no",
                },
            )

        if __name__ == "__main__":
            uvicorn.run(app, host=os.environ.get("COLLAB_PROXY_HOST", "127.0.0.1"), port=18080, log_level="error")
    ''').lstrip()
    open("/root/px.py", "w", encoding="utf-8").write(proxy_src)
    sp.Popen("python3 /root/px.py", shell=True, stdout=open("px.log", "w"), stderr=sp.STDOUT)
    if wait_pt(18080, "Proxy", host=PROXY_HOST): log("✅", "AI Engine Online", f"Ready for requests on {health_host(PROXY_HOST)}")
    return True

def main():
    t0 = time.time()
    try:
        setup_env()
        setup_cf()
        if RUN_LLAMA and not init_ai(): sys.exit(1)

        if EN_WEB: sp.Popen(f'ttyd -i {WEB_HOST} -p 68 -t fontSize=22 bash', shell=True, stdout=open('ttyd.log', 'w'))

        urls = {}
        if EN_CF:
            if RUN_LLAMA:
                api_url = cf_tunnel(18080, host=PROXY_HOST)
                if api_url: urls["api"] = f"{api_url}/v1"
            if EN_WEB:
                urls["web"] = cf_tunnel(68, host=WEB_HOST)

        if EN_SSH:
            run("tmate -S /tmp/tmate.sock new-session -d")
            for _ in range(15):
                ssh = run("tmate -S /tmp/tmate.sock display -p '#{tmate_ssh}'").stdout.strip()
                if ssh.startswith("ssh"): urls["ssh"] = ssh; break
                time.sleep(1)

        print(f"\n\x1b[1;35m╔════════════════════════════════════════════════════════════╗\x1b[0m")
        print(f"\x1b[1;35m║\x1b[0m  ✨  \x1b[1;36mcollabLLM backend\x1b[0m  \x1b[2m— SETUP COMPLETE in {time.time()-t0:.1f}s\x1b[0m")
        if urls.get("api"): print(f"\x1b[1;35m╠════════════════════════════════════════════════════════════╣\n║\x1b[0m  🔑 API: \x1b[1;36m{urls['api']}\x1b[0m")
        if urls.get("web"): print(f"\x1b[1;35m║\x1b[0m  💻 ttyd: \x1b[1;36m{urls['web']}\x1b[0m")
        if urls.get("ssh"): print(f"\x1b[1;35m║\x1b[0m  🛠️ tmate: \x1b[1;36m{urls['ssh']}\x1b[0m")
        print(f"\x1b[1;35m╚════════════════════════════════════════════════════════════╝\x1b[0m\n")

        if urls.get("api"):
            print(f"\x1b[1;33m📋 Paste this link in collabLLM to connect:\x1b[0m")
            print(f"\x1b[1;36m   {urls['api']}\x1b[0m\n")
            print(f"\x1b[1;33m⚠️  Cold Start Notice: Preparing GPU VM, compiling packages, and downloading\x1b[0m")
            print(f"\x1b[1;33m   model weights can take 5 minutes or more. Please wait for the/v1 link to load.\x1b[0m\n")


        if EN_KEEP:
            while True:
                time.sleep(300)
                log("🟢", "Keep-Alive Daemon", "Services Nominal", "2")
    except KeyboardInterrupt:
        log("🛑", "Shutdown", "Received interrupt, cleaning up...", "1;33")
        run("pkill -9 -f llama_cpp; pkill -9 -f cloudflared; pkill -9 -f ttyd; pkill -9 -f tmux; pkill -9 -f tmate; pkill -9 -f px.py; pkill -9 -f uvicorn")
        print("\nShutdown complete.")

if __name__ == "__main__": main()





# Cold Start Notice

# Preparing the GPU VM, compiling packages, 
# and downloading uncensored model weights usually takes 5 minutes or more.
#  Please wait for the printed /v1 link to appear in your Colab output
#   before connecting
  
# Run the cells and wait for the backend link.


# then paste the link in the text box and enter




import asyncio
import json
import ollama
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SYSTEM_PROMPT = """Tu es un assistant superviseur VoIP expert Asterisk.
Tu dispos de plusieurs outils MCP pour consulter l'état du serveur Asterisk en temps réel et piloter les communications.
Règles :
1. Sois clair, concis et réponds toujours en français.
2. Utilise les outils MCP chaque fois qu'une information technique ou une action sur le serveur est requise.
3. Synthétise les résultats techniques (JSON) de manière lisible pour un opérateur humain."""

CRITICAL_TOOLS = ["hangup_channel", "make_call"]

async def main():
    server_params = StdioServerParameters(
        command="/home/melo/mcp-asterisk-server/venv/bin/python3",
        args=["/home/melo/mcp-asterisk-server/server.py"]
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            mcp_tools = await session.list_tools()
            ollama_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.inputSchema
                    }
                }
                for t in mcp_tools.tools
            ]

            print("\n=== Agent Supervision Asterisk Connecté ===")
            print(f"Outils MCP prêts : {[t.name for t in mcp_tools.tools]}\n")

            while True:
                user_input = input("Superviseur > ")
                if user_input.lower() in ["exit", "quit"]:
                    break

                response = ollama.chat(
                    model='qwen2.5:3b',
                    messages=[
                        {'role': 'system', 'content': SYSTEM_PROMPT},
                        {'role': 'user', 'content': user_input}
                    ],
                    tools=ollama_tools
                )

                msg = response['message']

                if msg.get('tool_calls'):
                    for call in msg['tool_calls']:
                        fn_name = call['function']['name']
                        fn_args = call['function']['arguments']
                        
                        # Validation "Humain dans la boucle" pour les outils critiques
                        if fn_name in CRITICAL_TOOLS:
                            confirm = input(f"⚠️ [SÉCURITÉ] Exécuter {fn_name} avec les arguments {fn_args} ? (o/n) : ")
                            if confirm.lower() not in ["o", "oui", "y"]:
                                print("Action annulée par l'opérateur.\n")
                                continue

                        print(f"\n[LLM Action] Exécution de : {fn_name}({fn_args})")
                        res = await session.call_tool(fn_name, arguments=fn_args)
                        
                        if res.content and len(res.content) > 0:
                            result_text = getattr(res.content[0], 'text', str(res.content[0]))
                        else:
                            result_text = "[]"
                            
                        print(f"[Résultat Asterisk] : {result_text}\n")

                        second_response = ollama.chat(
                            model='qwen2.5:3b',
                            messages=[
                                {'role': 'system', 'content': SYSTEM_PROMPT},
                                {'role': 'user', 'content': user_input},
                                msg,
                                {'role': 'tool', 'content': result_text}
                            ]
                        )
                        print(f"Assistant AI > {second_response['message']['content']}\n")
                else:
                    print(f"\nAssistant AI > {msg['content']}\n")

if __name__ == "__main__":
    asyncio.run(main())

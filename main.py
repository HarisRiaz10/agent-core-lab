"""
CloudLab Assistant powered by AgentCore + Strands
Debug-enhanced version with simpler print statements
"""

import os
import csv
import io
import boto3
import botocore
import traceback
from strands import Agent
from strands_tools.code_interpreter import AgentCoreCodeInterpreter
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig, RetrievalConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()
S3_BUCKET = "<your-s3-bucket-name>"
S3_KEY = "CloudLabs.csv"
MEMORY_ID = os.getenv("BEDROCK_AGENTCORE_MEMORY_ID")
REGION = os.getenv("AWS_REGION")
MODEL_ID = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"

def load_labs():
    """Load labs from local file or S3 with debug prints."""
    labs = []

    # Try S3
    print(f"Trying S3 bucket: {S3_BUCKET}/{S3_KEY}")
    try:
        s3_client = boto3.client("s3", region_name=REGION)
        resp = s3_client.get_object(Bucket=S3_BUCKET, Key=S3_KEY)
        text = resp["Body"].read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))
        labs = [row for row in reader]
        print(f"✅ Loaded {len(labs)} labs from S3")
        return labs
    except botocore.exceptions.ClientError as e:
        print(f"❌ S3 access failed: {e}")
    except Exception as e:
        print(f"⚠️ Unexpected S3 error: {e}")
        traceback.print_exc()

    print("⚠️ Could not load labs from local or S3")
    return labs


LABS = load_labs()


def recommend_labs(query, labs):
    """Recommend labs based on keyword overlap."""
    print("\n=== Recommending Labs ===")
    print(f"User query: {query}")
    q = query.lower()
    results = []

    for lab in labs:
        try:
            text = " ".join(str(v).lower() for v in lab.values())
            score = sum(1 for w in q.split() if w in text)
            if score > 0:
                results.append((score, lab))
        except Exception as e:
            print(f"⚠️ Error scoring lab: {e}")

    results.sort(key=lambda x: x[0], reverse=True)
    top = [lab for _, lab in results[:3]]

    print(f"Found {len(top)} relevant labs")
    for lab in top:
        print(f"- {lab.get('topic', lab.get('name', 'Unknown'))}")

    return top


@app.entrypoint
def invoke(payload, context):
    print("\n=== Invoking CloudLab Assistant ===")
    try:
        user_prompt = payload.get("prompt", "")
        print(f"User prompt: {user_prompt}")

        actor_id = "cloudlab-user"
        session_id = getattr(context, 'session_id', 'default')

        # Memory setup
        session_manager = None
        if MEMORY_ID:
            print("Initializing memory manager...")
            try:
                memory_config = AgentCoreMemoryConfig(
                    memory_id=MEMORY_ID,
                    session_id=session_id,
                    actor_id=actor_id,
                    retrieval_config={
                        f"/users/{actor_id}/aws-knowledge": RetrievalConfig(top_k=3, relevance_score=0.5)
                    },
                )
                session_manager = AgentCoreMemorySessionManager(memory_config, REGION)
                print("✅ Memory manager ready")
            except Exception as e:
                print(f"⚠️ Memory setup failed: {e}")
                traceback.print_exc()

        # Code interpreter
        print("Initializing code interpreter...")
        code_interpreter = None
        try:
            code_interpreter = AgentCoreCodeInterpreter(region=REGION, session_name=session_id, auto_create=True)
            print("✅ Code interpreter ready")
        except Exception as e:
            print(f"⚠️ Code interpreter failed: {e}")
            traceback.print_exc()

        # Recommend labs
        recommended = recommend_labs(user_prompt, LABS)

        # Build context
        context_info = ""
        if recommended:
            for lab in recommended:
                name = lab.get("Name") # Name,Link,Summary,Lab Description
                url = lab.get("Link")
                context_info += f"- [{name}]({url})({lab.get('Summary')})\n"

        system_prompt = (
            "You are CloudLab Assistant — an AWS learning guide.\n"
            "When possible, recommend relevant CloudLabs as Markdown links."
        )

        print("Creating agent...")
        agent = Agent(
            model=MODEL_ID,
            session_manager=session_manager,
            system_prompt=system_prompt,
            tools=[code_interpreter.code_interpreter] if code_interpreter else [],
        )

        print("Running agent query...")
        result = agent(user_prompt + "\n\n" + context_info)
        print("Agent completed successfully.")

        response_text = result.message.get("content", [{}])[0].get("text", str(result))
        print(f"Response preview: {response_text[:150]}")

        return {"response": response_text}

    except Exception as e:
        print(f"❌ invoke() crashed: {e}")
        traceback.print_exc()
        return {"error": str(e)}


if __name__ == "__main__":
    print("\n=== Starting CloudLab Assistant ===")
    print(f"Region: {REGION}, Model: {MODEL_ID}, Memory ID: {MEMORY_ID}")
    print(f"Labs loaded: {len(LABS)}")
    app.run()

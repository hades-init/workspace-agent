import time
import logging

from langchain.messages import HumanMessage
from anthropic._exceptions import OverloadedError


logger = logging.getLogger(__name__)


class ExtractionError(Exception):
    """LLM extraction failed to produce valid structured output."""
    pass



# retry logic for anthropic OverloadError
def retry(func, max_retries=3):
    def _wrapper(*args, **kwargs):
        for attempt in range(max_retries):
            try:
                response = func(*args, **kwargs)
                return response
            except OverloadedError:
                if attempt == max_retries - 1:
                    raise
                wait = 2 ** attempt     # 1s, 2s, 4s ...
                logger.warning("Anthropic client overloaded, retrying in %ds ...", wait)
                time.sleep(wait)
    return _wrapper
                
@retry
def invoke_agent_with_retry(agent, input_message):
    return agent.invoke(
        {"messages": [HumanMessage(content=input_message)]}
)
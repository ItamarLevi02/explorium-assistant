import os
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

async def run_standard_agent(user_product_info: str, target_company_name: str) -> dict:
    """
    Runs a standard LLM call without Explorium tools to generate a sales email
    and returns the result in a structured dictionary matching the final_email_draft format.
    """
    print("--- Running Standard Agent ---")
    try:
        # Load environment variables
        load_dotenv()
        anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        
        if not anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables.")
        
        # Initialize the Chat Model with explicit API key
        llm = ChatAnthropic(
            model="claude-3-5-sonnet-20240620",
            temperature=0.7,
            api_key=anthropic_api_key
        )

        # Define a simple prompt template asking ONLY for the body
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful assistant tasked with writing a brief sales outreach email body."),
            ("human", """Please write a short (3-5 sentence) sales email body based on the following information:

            My Product Info: {product_info}
            Target Company: {target_company}

            The goal of the email is to briefly introduce the product and ask for a short meeting.
            Focus on a general value proposition. Do not invent specific details about the target company.
            Output ONLY the email body text. Do not include subject line, greetings, sign-offs, or any other text.""")
        ])

        # Simple chain: prompt -> LLM -> string output
        chain = prompt_template | llm | StrOutputParser()

        # Invoke the chain to get the body
        email_body = await chain.ainvoke({
            "product_info": user_product_info,
            "target_company": target_company_name
        })
        email_body = email_body.strip() # Clean extra whitespace

        print(f"--- Standard Agent generated body: {email_body[:100]}...")

        # Construct a basic Subject
        subject = f"Quick Question regarding {target_company_name}"

        # Create the structured output dictionary
        output = {
            "recipients": "[Not Applicable - Standard Agent]", # Placeholder for recipients
            "subject": subject,
            "body": email_body,
            "recipient_name": "[N/A]",  # Placeholder key
            "recipient_title": "[N/A]" # Placeholder key
        }

        return output

    except Exception as e:
        print(f"--- Standard Agent Error: {e}")
        # Return error in the same structure
        return {
            "recipients": "[Error]",
            "subject": "[Error]",
            "body": f"Error generating email with standard agent: {e}",
            "recipient_name": "[Error]",
            "recipient_title": "[Error]"
        }

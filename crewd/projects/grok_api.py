"""
Groq API Integration for tech stack analysis
"""
import os
from openai import OpenAI
from accounts.models import TECH_CHOICES

def analyze_tech_stack(description):
    """
    Analyze a project description with Groq API to suggest a tech stack from predefined choices
    
    Args:
        description (str): Project description text
        
    Returns:
        list: List of suggested technologies from TECH_CHOICES
    """
    try:
        # Create OpenAI client with Groq endpoint
        client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=os.environ.get("GROQ_API_KEY"))
        
        # Prepare the tech choices as a formatted string
        tech_choices_str = ", ".join(TECH_CHOICES)
        
        # Send request to Groq API
        response = client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[
                {
                    "role": "system",
                    "content": f"""You are a tech stack advisor. Based on the project description, recommend the most appropriate technologies from the following list: {tech_choices_str}

Your task is to:
1. Analyze the project description carefully
2. Select only technologies from the provided list that are most relevant
3. Consider both explicit mentions and implicit requirements
4. Return only 3-7 most important technologies
5. Format the response as a comma-separated list
6. Only include technologies that are in the provided list

Example response format: "Python, Django, PostgreSQL, React"
"""
                },
                {
                    "role": "user",
                    "content": description
                }
            ],
            max_tokens=200,
            temperature=0.3  # Lower temperature for more focused results
        )
        
        # Extract and clean the result
        suggested_tech = response.choices[0].message.content.strip()
        
        # Split into list and validate against TECH_CHOICES
        tech_list = [tech.strip() for tech in suggested_tech.split(',')]
        validated_tech = [tech for tech in tech_list if tech in TECH_CHOICES]
        
        return validated_tech
    
    except Exception as e:
        # Log the error and re-raise it
        print(f"Error analyzing tech stack: {str(e)}")
        raise e
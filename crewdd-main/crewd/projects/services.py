import os
from typing import List
from groq import Groq

class ProjectTaggingService:
    def __init__(self):
        self.client = Groq(
            api_key="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"
        )

    def generate_tags(self, project_description: str) -> List[str]:
        """
        Analyzes project description using Groq API and returns relevant tech stack tags.
        """
        prompt = f"""
        Analyze the following project description and extract relevant technology stack tags.
        Focus on programming languages, frameworks, tools, and technical skills required.
        Return only the tags as a comma-separated list.
        
        Project Description:
        {project_description}
        
        Example format: python, django, react, aws, machine-learning
        """

        try:
            response = self.client.chat.completions.create(
                messages=[{
                    "role": "system",
                    "content": "You are a technical project analyzer. Extract relevant technology stack tags from project descriptions."
                }, {
                    "role": "user",
                    "content": prompt
                }],
                model="mixtral-8x7b-32768",
                temperature=0.3,
                max_tokens=100
            )
            
            # Extract tags from response
            tags_string = response.choices[0].message.content.strip()
            return [tag.strip().lower() for tag in tags_string.split(',')]
        except Exception as e:
            print(f"Error generating tags: {str(e)}")
            return []

    def get_profile_recommendations(self, project_tags: List[str], user_profiles: List[dict]) -> List[dict]:
        """
        Matches project tags with user profiles to generate recommendations.
        """
        recommendations = []
        for profile in user_profiles:
            # Get profile skills as a list
            profile_skills = [skill.strip().lower() for skill in profile.get('skills', '').split(',')]
            
            # Calculate match score based on overlapping skills
            matching_skills = set(profile_skills).intersection(set(project_tags))
            match_score = len(matching_skills) / len(project_tags) if project_tags else 0
            
            if match_score > 0:
                recommendations.append({
                    'profile': profile,
                    'match_score': match_score * 100,  # Convert to percentage
                    'matching_skills': list(matching_skills)
                })
        
        # Sort recommendations by match score
        recommendations.sort(key=lambda x: x['match_score'], reverse=True)
        return recommendations 
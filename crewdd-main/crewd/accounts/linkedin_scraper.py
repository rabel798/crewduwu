"""
LinkedIn Profile Scraper for Skills
"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import os

def setup_driver():
    """Setup Chrome driver with necessary options"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=chrome_options)

def extract_skills_from_linkedin(profile_url, linkedin_email=None, linkedin_password=None):
    """
    Extract skills from a LinkedIn profile
    
    Args:
        profile_url (str): URL of the LinkedIn profile
        linkedin_email (str, optional): LinkedIn login email
        linkedin_password (str, optional): LinkedIn login password
        
    Returns:
        list: List of skills found on the profile
    """
    driver = setup_driver()
    skills = []
    
    try:
        driver.get(profile_url)
        
        # Login if credentials provided
        if linkedin_email and linkedin_password:
            try:
                # Wait for login button and click it
                login_button = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a[href='/login']"))
                )
                login_button.click()
                
                # Fill in credentials
                email_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "username"))
                )
                password_input = driver.find_element(By.ID, "password")
                
                email_input.send_keys(linkedin_email)
                password_input.send_keys(linkedin_password)
                
                # Submit login form
                driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
                time.sleep(3)  # Wait for login to complete
            except Exception as e:
                print(f"Login failed: {str(e)}")
                # Continue anyway as the profile might be public
        
        # Scroll to skills section
        try:
            skills_section = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "section.pv-profile-section.skills-section"))
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", skills_section)
            time.sleep(2)  # Wait for any animations
            
            # Try to click "Show more skills" button if it exists
            try:
                show_more_button = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".pv-skills-section__chevron-icon"))
                )
                driver.execute_script("arguments[0].click();", show_more_button)
                time.sleep(2)  # Wait for skills to expand
            except TimeoutException:
                print("No 'Show more skills' button found - proceeding with visible skills")
            
            # Extract skills using the reliable selector
            skill_elements = driver.find_elements(By.XPATH, "//*[starts-with(@class,'pv-skill-category-entity__name-text')]")
            skills = [skill.text.strip() for skill in skill_elements if skill.text.strip()]
            
        except TimeoutException:
            print("Could not find skills section")
            return []
            
    except Exception as e:
        print(f"Error scraping LinkedIn profile: {str(e)}")
        return []
        
    finally:
        driver.quit()
    
    return list(set(skills))  # Remove duplicates 
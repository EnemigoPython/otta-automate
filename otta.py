from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from webdriver_manager.firefox import GeckoDriverManager
from dotenv import load_dotenv
from enum import Enum, auto
import traceback
import pathlib
import logging
import json
import sys
import os

FILENAME = os.path.basename(__file__)
AUTO = "--auto" in sys.argv
DEBUG = "--debug" in sys.argv
with open("config.json", "r") as f:
    CONFIG = json.load(f)

def get_logger():
    logger = logging.getLogger(FILENAME)
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler("otta-automate.log")
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

class InputType(Enum):
    TEXTAREA = auto()
    CHECKBOX = auto()
    DROPDOWN = auto()
    UNKNOWN = auto()

class Sentiment(Enum):
    COVER_LETTER = auto()
    AFFIRM_RIGHT_TO_WORK = auto()
    NEED_SPONSORSHIP = auto()
    HOW_DID_YOU_HEAR = auto()
    PRONOUNS = auto()
    UNKNOWN = auto()

class Question:
    """
    A Question object represents what needs to be entered (Sentiment) and how to enter it (InputType)
    """

    def __init__(self, input_type: InputType, sentiment: Sentiment):
        self.input_type = input_type
        self.sentiment = sentiment

    def __repr__(self):
        return f"(input type: {self.input_type.name}, sentiment: {self.sentiment.name})"

class NoCredentialsException(Exception):
    """A custom error to reject execution if the proper env variables aren't set"""
    def __init__(self):
        super().__init__("You need 'PROFILE_FILE' and 'USER' environment variables set to run this script")

class DriverManager(webdriver.Firefox):
    """A wrapper to run the Selenium driver as a context manager and inject our logger"""
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        try:
            options = FirefoxOptions()
            if (profile := os.getenv("PROFILE_FILE")) and (user := os.getenv("USER")):
                self.logger.info(f"Using profile found for {user}: {profile}")
                pathroot = pathlib.WindowsPath(r"C:\\")
                path = pathroot / "Users" / user / "AppData" / "Local" / "Mozilla" / "Firefox" / "Profiles" / profile
                options.add_argument("--profile")
                options.add_argument(str(path))
            else:
                raise NoCredentialsException()
            super().__init__(service=FirefoxService(GeckoDriverManager().install()), options=options)
            self.implicitly_wait(CONFIG.get("wait") or 30)
            self.logger.info("Driver initialised")
        except Exception as e:
            self.logger.error(f"Crashed on startup with a {repr(e.__class__.__name__)}: view traceback below")
            self.logger.error(traceback.format_exc())
            raise e
    
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if any(exc):
            # we get the name of an exception with e.__class__.__name__, but exc[0] is not of type Exception
            self.logger.error(f"Script crashed with a {repr(exc[0].__name__)}: view traceback below")
            self.logger.error(traceback.format_exc())
        else:
            self.logger.info("Script ran to completion: exiting")
        self.quit()

    def debug(self, message: str, level=logging.INFO):
        """Breakpoint for debug mode"""
        if DEBUG:
            self.logger.log(level, message)
            breakpoint()

    def find_element_by_data_id(self, id: str):
        """Find a SINGLE element using an xpath pattern on the `data-testid` tag"""
        return self.find_element(By.XPATH, f"//*[@data-testid='{id}']")

    def find_elements_by_data_id(self, id: str):
        """Find MULTIPLE elements using an xpath pattern on the `data-testid` tag"""
        return self.find_elements(By.XPATH, f"//*[@data-testid='{id}']")

    def page_data_text(self, el: str):
        """
        Extract the text from a `data-testid`, or an empty string if it isn't possible
        """
        try:
            return self.find_element_by_data_id(el).text
        except:
            return ""

    def page_data_text_list(self, el: str):
        """
        Extract a list of text from tags with `data-testid` or an empty list if it isn't possible
        """
        try:
            return [i.text for i in self.find_elements_by_data_id(el)]
        except:
            return []

    def get_web_link(self):
        """
        Attempt to get the web link of a company or return None
        """
        try:
            job_card = self.find_element_by_data_id("job-card")
            link = job_card.find_element(By.TAG_NAME, "a")
            return link.get_attribute("href")
        except:
            return None

    def extract_input_type(self, text: str):
        try:
            input_instructions = text.split("\n")[-1].lower()
            if "choose an option" in input_instructions:
                return InputType.DROPDOWN
            if "check all" in input_instructions:
                return InputType.CHECKBOX
            if "type your answer" in input_instructions:
                return InputType.TEXTAREA
            self.logger.warning(f"Couldn't identify the input type for a question: {text}")
            return InputType.UNKNOWN
        except IndexError:
            self.logger.warning(f"Couldn't identify the input type for a question: {text}")
            return InputType.UNKNOWN

    def extract_sentiment(self, text: str):
        sentiment = Sentiment.UNKNOWN
        semantic_clues = {
            Sentiment.COVER_LETTER: ["why do you want to work"],
            Sentiment.AFFIRM_RIGHT_TO_WORK: ["right to work in UK", "do have", "do you have", "citizenship", "confirm the right", "confirm you are"],
            Sentiment.NEED_SPONSORSHIP: ["will you need", "sponsor", "sponsorship", "immigration"],
            Sentiment.PRONOUNS: ["preferred name", "pronouns"],
            Sentiment.HOW_DID_YOU_HEAR: ["how did you hear"]
        }
        threshold = 0
        for key, value in semantic_clues.items():
            hits = sum(1 for s in value if s in text.lower())
            if hits > threshold:
                threshold = hits
                sentiment = key
        if threshold == 0:
            self.logger.warning(f"Couldn't identify the sentiment for a question: {text}")
        return sentiment

    def extract_question_info(self, elements: list[WebElement]):
        """
        We want to find out the meaning of the question and the type of input so we can boil it down
        to a Question object
        """
        for element in elements:
            yield Question(
                self.extract_input_type(element.text), 
                self.extract_sentiment(element.text)
            )

    def enter_answer(self, element: WebElement, input_type: InputType, answer: str):
        pass

class JobApplication:
    """Used to gather the data and formulate our job application"""
    def __init__(self, driver: DriverManager):
        self.job_title = driver.page_data_text("job-title") or None
        try:
            self.company_title = driver.page_data_text("ottas-take").split("Otta's take on ")[-1]
        except IndexError:
            self.company_title = None
        self.technologies = driver.page_data_text("job-technology-used").split("\n") or None
        self.office_requirements = driver.page_data_text("office-day-requirements") or None
        self.salary = driver.page_data_text("salary-section").split("k")[0] or None
        if self.salary is not None:
            self.salary += 'k'
        self.location_description = driver.page_data_text_list("job-location-tag")
        self.industries = driver.page_data_text_list("company-sector-tag")
        self.benefits = driver.page_data_text_list("company-benefit-bullet")
        self.values = driver.page_data_text_list("company-value-bullet")
        self.job_involves = driver.page_data_text_list("job-involves-bullet")
        self.job_requirements = driver.page_data_text_list("job-requirements-bullet")
        self.web_link = driver.get_web_link()
        if self.company_title:
            driver.logger.info(f"Data gathered for {self.company_title}")

    def minimum_application_requirement(self):
        return self.job_title is not None and self.company_title is not None

    def answers(self, questions: list[Question]):
        for question in questions:
            if question.input_type == InputType.TEXTAREA:
                pass
            else:
                pass
            yield question.sentiment

def main():
    logger = get_logger()
    logger.info(f"Started execution of {FILENAME}")
    logger.info(f"Execution mode: '{'automatic' if AUTO else 'manual'}', debug mode: '{'on' if DEBUG else 'off'}'")
    load_dotenv()

    with DriverManager(logger) as driver:
        driver.get("https://app.otta.com/jobs/theme/apply-via-otta")
        applications_in_session = 0
        while (application := JobApplication(driver)).minimum_application_requirement():
            driver.debug(f"Entering debugger at '{application.company_title}' listing page")
            buttons_panel = driver.find_element_by_data_id("desktop-action-panel")
            buttons_panel.find_elements(By.TAG_NAME, "button")[1].click()
            apply_modal = driver.find_element_by_data_id("apply-content")
            apply_modal.find_element(By.TAG_NAME, "button").click()
            question_elements = driver.find_elements_by_data_id("application-questions-card")
            questions = [question for question in driver.extract_question_info(question_elements)]
            answers = [answer for answer in application.answers(questions)]
            driver.debug(f"Entering debugger at '{application.company_title}' application page")
            for element, question, answer in zip(question_elements, questions, answers):
                driver.enter_answer(element, question.input_type, answer)
            applications_in_session += 1
        if applications_in_session > 0:
            logger.info(f"{applications_in_session} job applications made in this session")
        else:
            logger.warning("No job applications made - might be an error or new posts might have been depleted")
            driver.debug("Entering debugger to investigate incident", logging.WARNING)


if __name__ == '__main__':
    main()

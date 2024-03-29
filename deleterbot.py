import praw
import smtplib
import datetime
import urllib.request
import os
import imghdr
from email.message import EmailMessage
from time import sleep
from config import dbconstants as config

# non-config constants
SECONDS_IN_MONTH = 2592000  # pretending all months are 30 days exactly


def send_an_email(message, subject, attachment=None):
    mail_server = smtplib.SMTP('localhost')
    msg = EmailMessage()
    msg['From'] = config.EMAIL_SENDER
    msg['To'] = config.EMAIL_RECIPIENT
    msg['Subject'] = subject
    msg.set_content(message)
    if attachment is not None:
        with open(attachment, 'rb') as fp:
            img_data = fp.read()
        msg.add_attachment(img_data, maintype='image', subtype=imghdr.what(None, img_data))
    mail_server.send_message(msg)
    mail_server.quit()


def handle_post(post_to_handle):
    msg = "Title: " + str(post_to_handle.title) + "\n"
    msg += "Score: " + str(post_to_handle.score) + "\n"
    msg += "Comments: " + str(post_to_handle.num_comments) + "\n"
    msg += "Subreddit: " + str(post_to_handle.subreddit.display_name) + "\n"
    msg += "Posted at: " + str(post_to_handle.created_utc) + " UTC\n"
    msg += "Content:\n"
    if post_to_handle.is_self:
        msg += str(post_to_handle.selftext)
    else:
        msg += str(post_to_handle.url)
    return msg


def handle_comment(cmt_to_handle):
    post_permalink = cmt_to_handle.submission.permalink
    msg = "Source Post: " + str(post_permalink) + "\n"
    msg += "Subreddit: " + str(cmt_to_handle.subreddit.display_name) + "\n"
    post_id = cmt_to_handle.link_id
    parent_id = cmt_to_handle.parent_id
    if post_id not in parent_id:  # i.e., the parent is another comment, not the submission
        parent_true_id = parent_id.split('_')
        parent_true_id = parent_true_id[1]
        parent_permalink = post_permalink + parent_true_id + "/"
        msg += "Parent Comment ID: " + str(parent_permalink) + "\n"
    msg += "Score: " + str(cmt_to_handle.score) + "\n"
    msg += "Posted at: " + str(cmt_to_handle.created_utc) + " UTC\n"
    msg += "Content:\n"
    msg += str(cmt_to_handle.body)
    return msg


def craft_message(r_obj):
    if isinstance(r_obj, praw.models.Submission):
        return handle_post(r_obj)
    else:
        return handle_comment(r_obj)


# main
r = praw.Reddit(user_agent=config.USER_AGENT, client_id=config.CLIENT_ID, client_secret=config.CLIENT_SECRET,
                username=config.REDDIT_USER, password=config.REDDIT_PW)

try:
    while True:
        rdtr = r.redditor('versorverbi')
        posts = rdtr.submissions.new()
        rightnow = datetime.datetime.utcnow()
        rightnow_timestamp = (rightnow - datetime.datetime(1970, 1, 1)) / datetime.timedelta(seconds=1)
        for post in posts:
            post_time = post.created_utc
            if rightnow_timestamp - post_time >= SECONDS_IN_MONTH:
                filename = None
                if not post.is_self:
                    if 'redd.it' in post.url:
                        filename = post.url.split('/')
                        filename = filename[len(filename)-1]
                        filename = os.path.join(os.path.expanduser('~'), filename)
                        urllib.request.urlretrieve(post.url, filename)
                send_an_email(craft_message(post), post.title, filename)
                if post.is_self:
                    post.edit("[removed]")
                post.delete()
                if filename is not None:
                    os.remove(filename)
        cmts = rdtr.comments.new()
        for cmt in cmts:
            cmt_time = cmt.created_utc
            if rightnow_timestamp - cmt_time >= SECONDS_IN_MONTH:
                send_an_email(craft_message(cmt), "Comment on: " + cmt.submission.title)
                cmt.edit("[removed]")
                cmt.delete()
        sleep(86400)  # there's no good reason to check this more often than 1/day
except Exception as e:
    print(e)
    send_an_email(str(e), 'Exception thrown')

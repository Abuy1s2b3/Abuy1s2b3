import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler
import config
from image_converter import ImageConverter
from pdf_converter import PDFConverter
import uuid
import telegram

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def is_user_in_channel(bot, user_id):
    """Check if user is member of the required channel"""
    try:
        member = bot.get_chat_member(chat_id=config.CHANNEL_ID, user_id=user_id)
        logger.info(f"Channel membership status for user {user_id}: {member.status}")
        return member.status in ['member', 'administrator', 'creator']
    except telegram.error.BadRequest as e:
        logger.error(f"BadRequest error checking channel membership: {str(e)}")
        if "Chat not found" in str(e):
            logger.error(f"Channel {config.CHANNEL_ID} not found. Please verify the channel ID.")
        return False
    except telegram.error.Unauthorized as e:
        logger.error(f"Unauthorized error: {str(e)}. Bot might not be an admin in the channel.")
        return False
    except Exception as e:
        logger.error(f"Error checking channel membership: {str(e)}")
        return False

def start(update: Update, context: CallbackContext):
    """Send a message when the command /start is issued."""
    keyboard = [
        [InlineKeyboardButton("Join Our Channel", url=config.CHANNEL_LINK)],
        [InlineKeyboardButton("✅ Verify Membership", callback_data='verify_membership')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_message = (
        "👋 Welcome to the Image to PDF Bot!\n\n"
        "To use this bot, please:\n"
        "1. Join our channel first\n"
        "2. Click the verify button below\n"
        "3. Start converting your images!\n\n"
        "Supported formats: JPG, JPEG, PNG\n"
        "Maximum file size: 20MB"
    )
    update.message.reply_text(welcome_message, reply_markup=reply_markup)

def verify_membership(update: Update, context: CallbackContext):
    """Verify if user has joined the channel"""
    query = update.callback_query

    try:
        # Check if bot has access to the channel
        try:
            chat = context.bot.get_chat(config.CHANNEL_ID)
            logger.info(f"Successfully accessed channel: {chat.title}")
        except telegram.error.BadRequest as e:
            logger.error(f"Cannot access channel: {str(e)}")
            query.answer("⚠️ Bot configuration error. Please contact admin.", show_alert=True)
            return

        # Verify membership
        if is_user_in_channel(context.bot, update.effective_user.id):
            # Create keyboard with all conversion options
            keyboard = [
                [
                    InlineKeyboardButton("🖼️ Image to PDF", callback_data='convert_image'),
                    InlineKeyboardButton("📝 PDF to Text", callback_data='convert_to_text')
                ],
                [
                    InlineKeyboardButton("📊 PDF to CSV", callback_data='convert_to_csv'),
                    InlineKeyboardButton("🔄 Merge PDFs", callback_data='merge_pdfs')
                ],
                [
                    InlineKeyboardButton("❓ Help", callback_data='show_help'),
                    InlineKeyboardButton("🌟 More Options", callback_data='more_options')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            success_message = (
                "✅ Membership verified!\n\n"
                "Choose a conversion option:\n"
                "• Image to PDF: Convert your images\n"
                "• PDF to Text: Extract text from PDFs\n"
                "• PDF to CSV: Convert tables to spreadsheets\n"
                "• Merge PDFs: Combine multiple PDFs\n\n"
                "Or simply send me your files directly!"
            )
            query.edit_message_text(text=success_message, reply_markup=reply_markup)
        else:
            keyboard = [
                [InlineKeyboardButton("Join Our Channel", url=config.CHANNEL_LINK)],
                [InlineKeyboardButton("🔄 Check Again", callback_data='verify_membership')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            error_message = (
                "❌ You haven't joined our channel yet.\n\n"
                "Please join the channel first, then click 'Check Again'"
            )
            query.edit_message_text(text=error_message, reply_markup=reply_markup)

    except telegram.error.BadRequest as e:
        if "Message is not modified" in str(e):
            query.answer("Status unchanged. Try again later.", show_alert=True)
        else:
            logger.error(f"Error in verify_membership: {str(e)}")
            query.answer("An error occurred. Please try again.", show_alert=True)
    except Exception as e:
        logger.error(f"Unexpected error in verify_membership: {str(e)}")
        query.answer("An error occurred. Please try again.", show_alert=True)

def handle_pdf_convert(update: Update, context: CallbackContext, convert_to='csv'):
    """Handle PDF conversion to text or CSV"""
    if not is_user_in_channel(context.bot, update.effective_user.id):
        start(update, context)
        return

    # Initialize variables
    temp_pdf_path = None
    output_path = None

    try:
        if not update.message.document:
            update.message.reply_text("❌ Please send a PDF file.")
            return

        document = update.message.document
        if not document.file_name.lower().endswith('.pdf'):
            update.message.reply_text("❌ Please send a valid PDF file.")
            return

        # Download the PDF file
        new_file = context.bot.get_file(document.file_id)
        temp_pdf_path = os.path.join(config.TEMP_DIR, f"{str(uuid.uuid4())}.pdf")
        new_file.download(temp_pdf_path)

        # Send processing message
        processing_message = update.message.reply_text("🔄 Processing your PDF...")

        # Convert based on requested format
        if convert_to == 'text':
            output_path = PDFConverter.pdf_to_text(temp_pdf_path)
            caption = "✅ Here's your text file!"
            filename = "converted.txt"
        else:  # csv
            output_path = PDFConverter.pdf_to_csv(temp_pdf_path)
            caption = "✅ Here's your CSV file!"
            filename = "converted.csv"

        # Send the converted file
        with open(output_path, 'rb') as converted_file:
            update.message.reply_document(
                document=converted_file,
                filename=filename,
                caption=caption
            )

        # Clean up
        PDFConverter.cleanup_files([temp_pdf_path, output_path])
        context.bot.delete_message(
            chat_id=update.message.chat_id,
            message_id=processing_message.message_id
        )

    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}")
        update.message.reply_text(
            "❌ Sorry, something went wrong while processing your PDF. Please try again."
        )
        # Clean up in case of error
        if temp_pdf_path:
            PDFConverter.cleanup_files([temp_pdf_path])
        if output_path:
            PDFConverter.cleanup_files([output_path])

def pdf_to_text(update: Update, context: CallbackContext):
    """Convert single PDF to text"""
    if not is_user_in_channel(context.bot, update.effective_user.id):
        start(update, context)
        return

    try:
        if not update.message.document:
            update.message.reply_text("❌ Please send a PDF file.")
            return

        document = update.message.document
        if not document.file_name.lower().endswith('.pdf'):
            update.message.reply_text("❌ Please send a valid PDF file.")
            return

        # Check file size
        if document.file_size > config.MAX_FILE_SIZE:
            update.message.reply_text("❌ File is too big. Maximum size is 20MB.")
            return

        # Send processing message
        processing_message = update.message.reply_text("🔄 Converting PDF to text...")

        # Download and process the file
        temp_pdf_path = os.path.join(config.TEMP_DIR, f"{str(uuid.uuid4())}.pdf")
        context.bot.get_file(document.file_id).download(temp_pdf_path)

        # Convert to text
        output_path = PDFConverter.pdf_to_text(temp_pdf_path)

        # Send the text file
        with open(output_path, 'rb') as text_file:
            update.message.reply_document(
                document=text_file,
                filename=f"{os.path.splitext(document.file_name)[0]}.txt",
                caption="✅ Here's your text file!"
            )

        # Clean up
        for file_path in [temp_pdf_path, output_path]:
            if os.path.exists(file_path):
                os.remove(file_path)

        # Delete processing message
        context.bot.delete_message(
            chat_id=update.message.chat_id,
            message_id=processing_message.message_id
        )

    except Exception as e:
        logger.error(f"Error converting PDF to text: {str(e)}")
        update.message.reply_text(
            "❌ Sorry, something went wrong while converting your PDF. Please try again."
        )

def pdf_to_csv(update: Update, context: CallbackContext):
    """Convert PDF to CSV"""
    handle_pdf_convert(update, context, 'csv')

def merge_pdfs_command(update: Update, context: CallbackContext):
    """Start the PDF merge process"""
    if not is_user_in_channel(context.bot, update.effective_user.id):
        start(update, context)
        return

    if not hasattr(context.user_data, 'pdf_files'):
        context.user_data['pdf_files'] = []

    context.user_data['pdf_files'] = []  # Reset the list
    update.message.reply_text(
        "🔄 Send me the PDFs you want to merge (one by one).\n"
        "When you're done, send /donemerge to merge them all."
    )

def done_merge_command(update: Update, context: CallbackContext):
    """Complete the PDF merge process"""
    if not is_user_in_channel(context.bot, update.effective_user.id):
        start(update, context)
        return

    if not hasattr(context.user_data, 'pdf_files') or not context.user_data['pdf_files']:
        update.message.reply_text("❌ Please send some PDF files first, then use /donemerge")
        return

    try:
        # Send processing message
        processing_message = update.message.reply_text("🔄 Merging your PDFs...")

        # Merge PDFs
        merged_path = PDFConverter.merge_pdfs(context.user_data['pdf_files'])

        # Send merged file
        with open(merged_path, 'rb') as merged_file:
            update.message.reply_document(
                document=merged_file,
                filename="merged.pdf",
                caption="✅ Here's your merged PDF!"
            )

        # Clean up
        PDFConverter.cleanup_files(context.user_data['pdf_files'] + [merged_path])
        context.user_data['pdf_files'] = []  # Reset the list
        context.bot.delete_message(
            chat_id=update.message.chat_id,
            message_id=processing_message.message_id
        )

    except Exception as e:
        logger.error(f"Error merging PDFs: {str(e)}")
        update.message.reply_text(
            "❌ Sorry, something went wrong while merging your PDFs. Please try again."
        )
        # Clean up in case of error
        if context.user_data.get('pdf_files'):
            PDFConverter.cleanup_files(context.user_data['pdf_files'])
        context.user_data['pdf_files'] = []

def handle_pdf_document(update: Update, context: CallbackContext):
    """Handle incoming PDF documents for merge"""
    if not is_user_in_channel(context.bot, update.effective_user.id):
        start(update, context)
        return

    if not hasattr(context.user_data, 'pdf_files'):
        context.user_data['pdf_files'] = []

    try:
        document = update.message.document
        if not document.file_name.lower().endswith('.pdf'):
            update.message.reply_text("❌ Please send only PDF files.")
            return

        # Download the PDF file
        new_file = context.bot.get_file(document.file_id)
        temp_pdf_path = os.path.join(config.TEMP_DIR, f"{str(uuid.uuid4())}.pdf")
        new_file.download(temp_pdf_path)

        # Add to list of files to merge
        context.user_data['pdf_files'].append(temp_pdf_path)

        # Send confirmation
        file_count = len(context.user_data['pdf_files'])
        update.message.reply_text(
            f"✅ PDF received! ({file_count} {'file' if file_count == 1 else 'files'} ready to merge)\n"
            "Send more PDFs or use /donemerge when finished."
        )

    except Exception as e:
        logger.error(f"Error handling PDF: {str(e)}")
        update.message.reply_text(
            "❌ Sorry, something went wrong while processing your PDF. Please try again."
        )

def help_command(update: Update, context: CallbackContext):
    """Send a message when the command /help is issued."""
    if not is_user_in_channel(context.bot, update.effective_user.id):
        start(update, context)
        return

    help_text = (
        "🔍 How to use this bot:\n\n"
        "1. Image to PDF:\n"
        "   • Send an image file\n"
        "   • Receive your PDF\n\n"
        "2. PDF to Text:\n"
        "   • Send a PDF file\n"
        "   • Use /totext command\n\n"
        "3. PDF to CSV:\n"
        "   • Send a PDF file\n"
        "   • Use /tocsv command\n\n"
        "4. Merge PDFs:\n"
        "   • Use /merge to start\n"
        "   • Send multiple PDFs\n"
        "   • Use /donemerge when finished\n\n"
        "Supported formats:\n"
        "• Images: JPG, JPEG, PNG\n"
        "• Convert from: PDF\n"
        "• Convert to: TXT, CSV\n"
        "Maximum file size: 20MB\n\n"
        "Commands:\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/totext - Convert PDF to text\n"
        "/tocsv - Convert PDF to CSV\n"
        "/merge - Start merging PDFs\n"
        "/donemerge - Complete PDF merge\n\n"
        "Note: You must remain a member of our channel to use the bot."
    )
    update.message.reply_text(help_text)

def handle_image(update: Update, context: CallbackContext):
    """Handle incoming images and convert them to PDF."""
    # Check channel membership first
    if not is_user_in_channel(context.bot, update.effective_user.id):
        start(update, context)
        return

    # Initialize variables
    temp_image_path = None
    pdf_path = None

    try:
        if update.message.photo:
            photo = update.message.photo[-1]
            file_id = photo.file_id
        elif update.message.document:
            document = update.message.document
            if not any(document.file_name.lower().endswith(ext) for ext in config.ALLOWED_FORMATS):
                update.message.reply_text("❌ Please send a valid image file (JPG, JPEG, or PNG).")
                return
            file_id = document.file_id
        else:
            update.message.reply_text("❌ Please send an image file.")
            return

        # Download the file
        new_file = context.bot.get_file(file_id)
        temp_image_path = os.path.join(config.TEMP_DIR, f"{str(uuid.uuid4())}_image{os.path.splitext(new_file.file_path)[1]}")
        new_file.download(temp_image_path)

        # Send processing message
        processing_message = update.message.reply_text("🔄 Processing your image...")

        # Convert to PDF
        pdf_path = ImageConverter.convert_to_pdf(temp_image_path)

        # Send the PDF file
        with open(pdf_path, 'rb') as pdf_file:
            update.message.reply_document(
                document=pdf_file,
                filename="converted.pdf",
                caption="✅ Here's your PDF!"
            )

        # Clean up
        ImageConverter.cleanup_files([temp_image_path, pdf_path])
        context.bot.delete_message(
            chat_id=update.message.chat_id,
            message_id=processing_message.message_id
        )

    except Exception as e:
        logger.error(f"Error processing image: {str(e)}")
        update.message.reply_text(
            "❌ Sorry, something went wrong while processing your image. Please try again."
        )
        # Clean up in case of error
        if temp_image_path:
            ImageConverter.cleanup_files([temp_image_path])
        if pdf_path:
            ImageConverter.cleanup_files([pdf_path])

def handle_conversion_callback(update: Update, context: CallbackContext):
    """Handle conversion button callbacks"""
    query = update.callback_query
    query.answer()

    if not is_user_in_channel(context.bot, update.effective_user.id):
        start(update, context)
        return

    action = query.data
    if action == 'convert_image':
        message = (
            "📸 Send me an image (JPG, JPEG, or PNG)\n"
            "I'll convert it to PDF for you!"
        )
        query.edit_message_text(text=message)
    elif action == 'convert_to_text':
        message = (
            "📄 Send me a PDF file\n"
            "I'll convert it to text for you!"
        )
        query.edit_message_text(text=message)
    elif action == 'convert_to_csv':
        message = (
            "📊 Send me a PDF file\n"
            "I'll convert it to CSV for you!"
        )
        query.edit_message_text(text=message)
    elif action == 'merge_pdfs':
        message = (
            "📚 Send me multiple PDF files one by one\n"
            "When you're done, use /donemerge to merge them!"
        )
        query.edit_message_text(text=message)
    elif action == 'show_help':
        help_text = (
            "🔍 Quick Guide:\n\n"
            "• Image to PDF: Send any image\n"
            "• PDF to Text: Send PDF, use /totext\n"
            "• PDF to CSV: Send PDF, use /tocsv\n"
            "• Merge PDFs: Use /merge, then send PDFs\n\n"
            "Type /help for more details!"
        )
        query.edit_message_text(text=help_text)
    elif action == 'more_options':
        message = "More options coming soon!"
        query.edit_message_text(text=message)
    else:
        message = "Invalid option selected. Please try again."
        query.edit_message_text(text=message)



def main():
    """Start the bot."""
    if not config.BOT_TOKEN:
        logger.error("Bot token not set! Please set your bot token in config.py")
        return

    # Create the Updater and pass it your bot's token
    updater = Updater(config.BOT_TOKEN)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # Add handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("totext", pdf_to_text))
    dp.add_handler(CommandHandler("tocsv", pdf_to_csv))
    dp.add_handler(CommandHandler("merge", merge_pdfs_command))
    dp.add_handler(CommandHandler("donemerge", done_merge_command))
    dp.add_handler(CallbackQueryHandler(verify_membership, pattern='^verify_membership$'))
    dp.add_handler(MessageHandler(Filters.photo | Filters.document.image, handle_image))
    dp.add_handler(MessageHandler(Filters.document.pdf, handle_pdf_document))
    dp.add_handler(CallbackQueryHandler(handle_conversion_callback)) #Added handler for conversion callbacks

    # Start the Bot
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()

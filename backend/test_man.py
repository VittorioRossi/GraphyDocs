import asyncio
from algorithms.package_analyzer import PackageAnalyzer
from utils.logging import get_logger

# Set up logging
logger = get_logger(__name__)


async def main():
    # Initialize the analyzer
    analyzer = PackageAnalyzer()

    try:
        # Replace this with the path you want to analyze
        root_directory = str("/Users/vittorio/Desktop/GraphyDocs/backend/utils")

        logger.info(f"Starting analysis of {root_directory}")

        # Run the analysis
        async for batch_update in analyzer.analyze(root_directory):
            logger.info(f"Batch status: {batch_update.status}")

            if batch_update.nodes:
                logger.info(f"Processed {len(batch_update.nodes)} nodes")

            if batch_update.edges:
                logger.info(f"Processed {len(batch_update.edges)} edges")

            if batch_update.processed_files:
                logger.info(
                    f"Successfully processed files: {batch_update.processed_files}"
                )

            if batch_update.failed_files:
                logger.warning(f"Failed files: {batch_update.failed_files}")

            if batch_update.statistics:
                logger.info(f"Statistics: {batch_update.statistics}")

            if batch_update.error:
                logger.error(f"Error: {batch_update.error}")

    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
    finally:
        # Cleanup
        await analyzer.stop()


if __name__ == "__main__":
    asyncio.run(main())

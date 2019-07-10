import asyncio

from piggy.piggy import Piggy


###
# Main - User defined function
###

async def main(pig):
    async for media in pig.feed():
        await pig.print(media)
#       await pig.like(media)
#       await pig.comment(media)
#       await pig.follow(media)

###
# Execution
###

loop = asyncio.get_event_loop()
pig = Piggy(loop)

try:
    loop.run_until_complete(pig.setup())
    loop.run_until_complete(pig.login())

    loop.create_task(pig.backup())
    loop.create_task(main(pig))

    loop.run_forever()

except KeyboardInterrupt:
    loop.run_until_complete(pig.close())

finally:
    for task in asyncio.Task.all_tasks():
        task.cancel()
    loop.run_until_complete(asyncio.wait(asyncio.Task.all_tasks()))
    loop.close()

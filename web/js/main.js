function buildImageFactory(imageData) {
    "use strict";
    const data = imageData.data,
        width = imageData.width;

    function getPixel(x,y) {
        const redIndex = (width * 4 * y) + (x * 4),
            greenIndex = redIndex + 1,
            blueIndex = greenIndex + 1;
        return [data[redIndex], data[greenIndex], data[blueIndex]];
    }

    const factory = {
        makeImagePiece(x1, y1, x2, y2) {
            function forEach(fn) {
                for (let x = x1; x <= x2; x++) {
                    for (let y = y1; y <= y2; y++) {
                        fn(getPixel(x,y));
                    }
                }
            }
            let average;
            return {
                x1, y1, x2, y2,
                getVariance() {
                    if (x2 - x1 < 5 || y2 - y1 < 5) {
                        return 0;
                    }
                    let min = Number.MAX_VALUE,
                        max = Number.MIN_VALUE;
                    forEach(p => {
                        const v = p[0] + p[1] + p[2];
                        min = Math.min(min, v);
                        max = Math.max(max, v);
                    });
                    return max - min;
                },
                getAverage() {
                    if (!average) {
                        let r=0,g=0,b=0,count=0;
                        forEach(p => {
                            r += p[0];
                            g += p[1];
                            b += p[2];
                            count++;
                        });
                        average = [r/count,g/count,b/count];
                    }
                    return average;
                },
                split() {
                    const xDiff = x2 - x1,
                        yDiff = y2 - y1;
                    if (xDiff < yDiff) {
                        const ySplit = Math.round((y1 + y2) / 2),
                            topPiece = factory.makeImagePiece(x1, y1, x2, ySplit),
                            bottomPiece = factory.makeImagePiece(x1, ySplit+1, x2, y2);
                        return [topPiece , bottomPiece];
                    } else {
                        const xSplit = Math.round((x1 + x2) / 2),
                            leftPiece = factory.makeImagePiece(x1, y1, xSplit, y2),
                            rightPiece = factory.makeImagePiece(xSplit+1, y1, x2, y2);
                        return [leftPiece , rightPiece];
                    }
                }
            };
        }
    };
    return factory;
}

const canvas = document.getElementById('canvas');
const video = document.getElementById('video');
const ctx = canvas.getContext('2d');

video.addEventListener('play', function() {
    const width = self.video.videoWidth * 2;
    const height = self.video.videoHeight * 2;
    const hiddenCanvas = document.createElement('canvas');
    canvas.width = hiddenCanvas.width = width;
    canvas.height = hiddenCanvas.height = height;
    const hiddenCtx = hiddenCanvas.getContext('2d');

    function computeFrame() {
        hiddenCtx.drawImage(video, 0, 0, width, height);
        let frame = hiddenCtx.getImageData(0, 0, width, height);
        draw(frame);
    }

    function timerCallback() {
        if (video.paused || video.ended) {
            return;
        }
        computeFrame();
        setTimeout(() => {
            timerCallback();
        }, 0);
    }

    timerCallback();
}, false);

function draw(imageData) {
    "use strict";
    const factory = buildImageFactory(imageData);

    const VARIANCE_THRESHOLD = 300, queue = [factory.makeImagePiece(0, 0, imageData.width - 1, imageData.height - 1)], finished = [];

    function processNext() {
        "use strict";
        const nextPiece = queue.shift(),
            variance = nextPiece.getVariance();
        if (variance < VARIANCE_THRESHOLD) {
            finished.push(nextPiece);
        } else {
            const [piece1, piece2] = nextPiece.split();
            queue.push(piece1);
            queue.push(piece2);
        }
    }

    while (queue.length) {
        processNext();
    }

    function sortByAverage(p1, p2) {
        return (p2[0] + p2[1] + p2[2]) - (p1[0] + p1[1] + p1[2]);
    }
    finished.sort(sortByAverage).forEach(nextPiece => {
        const avg = nextPiece.getAverage();
        ctx.beginPath();
        ctx.fillStyle = `rgb(${Math.round(avg[0])},${Math.round(avg[1])},${Math.round(avg[2])})`;
        ctx.fillRect(nextPiece.x1, nextPiece.y1, (nextPiece.x2 - nextPiece.x1 + 1), (nextPiece.y2 - nextPiece.y1 + 1))
        ctx.fill();
    })
}


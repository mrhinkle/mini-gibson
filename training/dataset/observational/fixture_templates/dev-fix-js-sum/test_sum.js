const assert=require('assert'); const {sum}=require('./sum');
assert.strictEqual(sum(2,3),5);
assert.strictEqual(sum(-1,1),0);
console.log('ok');

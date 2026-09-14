import {expect,it} from 'vitest'
import cases from '../../../../../../backend/tests/fixtures/studio-image-assets.json'
import {readImageAssetList} from '../lib/imageAssetContract'
it.each(cases)('matches the shared backend image contract: $id',testCase=>{
 expect(readImageAssetList(testCase.value)).toEqual(testCase.expected)
})

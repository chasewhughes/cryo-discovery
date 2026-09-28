import unittest
import numpy as np
from scripts.verify_matched_hydration import check_stereocenters

class MatchedStereoTests(unittest.TestCase):
    def test_periodic_translation_preserves_handedness_but_inversion_fails(self):
        coords=np.array([[[0,0,0],[.1,0,0],[0,.1,0],[0,0,.1],[-.1,-.1,-.1]]])
        box=np.eye(3)[None]*4
        volume=float(np.linalg.det(coords[0,1:4]-coords[0,4]))
        centers=[{'center_index':0,'neighbors':[1,2,3,4],'signed_volume_nm3':volume}]
        shifted=coords.copy();shifted[:,1,0]+=4
        self.assertTrue(check_stereocenters(shifted,box,centers)[0]['all_frames_preserve_starting_handedness'])
        flipped=coords.copy();flipped[:,:,0]*=-1
        with self.assertRaises(ValueError):check_stereocenters(flipped,box,centers)
        planar=coords.copy();planar[:,:,2]=0
        with self.assertRaises(ValueError):check_stereocenters(planar,box,centers)
if __name__=='__main__':unittest.main()
